#!/usr/bin/env python3
"""
Epic Private Internet Cash -- supply check (v1.1)

Checks, against YOUR OWN fully synced Epic node, that the coins that exist
match the published emission schedule. Python 3.8+, standard library only.

What it checks:
  1. Schedule   - recomputes the emission schedule and miner contribution from
                  the published rules (independent arithmetic, no node needed).
  2. Node state - the node is fully synced; reads the chain tip.
  3. Supply     - asks the node to re-verify the Mimblewimble supply equation
                  at the tip: sum(unspent outputs) - sum(kernel excesses)
                  - kernel_offset*G == (total issued by schedule)*H.
                  (/v1/chain/validate)
  4. Schedule vs node - compares the independently computed scheduled supply
                  with the figure the node reports.
  5. 2021 rollback - confirms the chain continues from block 861,141 and that
                  the two blocks rejected after the March 2021 incident are not
                  on it.
  6. Range proofs (optional, --sync-log) - confirms from the node's log that its
                  initial sync completed the full validation, which verifies the
                  range proof of every unspent output and every kernel signature.

Usage:
  python3 supply_check.py                       # node at http://127.0.0.1:3413
  python3 supply_check.py --node http://127.0.0.1:3413 \
          --secret ~/.epic/main/.api_secret --sync-log ~/.epic/main/epic-server.log
  python3 supply_check.py --schedule-only       # arithmetic only, no node
  python3 supply_check.py --json                # machine-readable output

Exit code 0 = all checks run passed, 1 = a check failed, 2 = could not run.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# 1. Published rules (EpicCash/epic, tag v4.1.2, core/src/consensus.rs)
# ---------------------------------------------------------------------------
EPIC_BASE = 100_000_000          # 1 EPIC = 10^8 base units
DAY = 1_440                      # blocks per day at the 60 s target
ERA_ENDS = [DAY * 334]
for days in (470, 601, 800, 1019):
    ERA_ENDS.append(ERA_ENDS[-1] + DAY * days)
ERA_REWARDS = [16 * EPIC_BASE, 8 * EPIC_BASE, 4 * EPIC_BASE, 2 * EPIC_BASE, 1 * EPIC_BASE]
ERA6_LENGTH = DAY * 1460
ERA6_BASE = 15_625_000           # 0.15625 EPIC

CONTRIB_FIRST = DAY * 120
CONTRIB_PERIOD = DAY * 365
CONTRIB_RATES = [888, 777, 666, 555, 444, 333, 222, 111, 111]   # per 10,000

EXPECTED_MAX_SUPPLY = 2_099_987_972_668_800        # 20,999,879.72668800 EPIC
EXPECTED_CONTRIB_TOTAL = 128_047_824_000_000       # 1,280,478.24 EPIC
CONTRIB_LAST_HEIGHT = CONTRIB_FIRST + 8 * CONTRIB_PERIOD   # 4,377,600

ROLLBACK_HEIGHT = 861_141
REJECTED_HEADERS = [
    "840cdf3ad968bd6895b07e4e3235ee704226f85c3163d2da2e6764c7e2b81ea2",
    "a98bbc899892d2553c52ef17cab6d708f9eaf7d575b3d62ca49bbf9d50ae55a7",
]


def block_reward(h):
    """Total reward of block h (miner share + contribution), in base units."""
    if h <= 0:
        return 0
    for end, reward in zip(ERA_ENDS, ERA_REWARDS):
        if h <= end:
            return reward
    exp = (h - ERA_ENDS[-1] - 1) // ERA6_LENGTH
    return ERA6_BASE >> exp if exp < 64 else 0


def scheduled_supply(height):
    """Total issued by the schedule in blocks 1..height (genesis pays nothing)."""
    total, prev = 0, 0
    for end, reward in zip(ERA_ENDS, ERA_REWARDS):
        if height > prev:
            total += (min(height, end) - prev) * reward
        prev = end
    if height > prev:
        remaining, reward = height - prev, ERA6_BASE
        while remaining > 0 and reward > 0:
            n = min(remaining, ERA6_LENGTH)
            total += n * reward
            remaining -= n
            reward //= 2
    return total


def contribution(h):
    """Miner contribution in block h (code name: foundation levy)."""
    if h <= 0:
        return 0
    if h <= CONTRIB_FIRST:
        idx = 0
    else:
        idx = (h - CONTRIB_FIRST - 1) // CONTRIB_PERIOD + 1
    if idx >= len(CONTRIB_RATES):
        return 0
    return block_reward(h) * CONTRIB_RATES[idx] // 10_000


def contribution_total():
    """Lifetime miner contribution, summed period by period (exact)."""
    total = 0
    for i, rate in enumerate(CONTRIB_RATES):
        start = 1 if i == 0 else CONTRIB_FIRST + (i - 1) * CONTRIB_PERIOD + 1
        end = CONTRIB_FIRST if i == 0 else CONTRIB_FIRST + i * CONTRIB_PERIOD
        h = start
        while h <= end:                       # constant reward within each era slice
            r = block_reward(h)
            seg_end = end
            for e in ERA_ENDS:
                if h <= e < seg_end:
                    seg_end = e
            total += (seg_end - h + 1) * (r * rate // 10_000)
            h = seg_end + 1
    return total


def onchain_issued(height):
    """Coins that exist on chain at `height`. The miner contribution is paid once
    every 1,440 blocks (in arrears), so blocks after the last daily payout have
    issued their miner share but not yet their contribution."""
    last_paid = (height // DAY) * DAY
    unpaid = sum(contribution(h) for h in range(last_paid + 1, height + 1))
    return scheduled_supply(height) - unpaid


def fmt(units):
    return f"{units // EPIC_BASE:,}.{units % EPIC_BASE:08d} EPIC"


def check_schedule():
    max_supply = scheduled_supply(10**12)
    contrib = contribution_total()
    ok = (max_supply == EXPECTED_MAX_SUPPLY and contrib == EXPECTED_CONTRIB_TOTAL
          and contribution(CONTRIB_LAST_HEIGHT) > 0 and contribution(CONTRIB_LAST_HEIGHT + 1) == 0)
    return {
        "name": "schedule",
        "passed": ok,
        "max_supply": fmt(max_supply),
        "miner_contribution_total": fmt(contrib),
        "miner_contribution_share_of_supply": f"{100 * contrib / max_supply:.2f}%",
        "miner_contribution_last_block": CONTRIB_LAST_HEIGHT,
    }

# ---------------------------------------------------------------------------
# Node access
# ---------------------------------------------------------------------------
class Node:
    def __init__(self, url, secret):
        self.url = url.rstrip("/")
        self.auth = None
        if secret:
            token = base64.b64encode(f"epic:{secret}".encode()).decode()
            self.auth = f"Basic {token}"

    def get(self, path, timeout=60):
        req = urllib.request.Request(self.url + path)
        if self.auth:
            req.add_header("Authorization", self.auth)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode() or "{}"
                return r.status, json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # /v1/status is public on some nodes; the owner-gated endpoints
                # (e.g. /v1/chain/validate) are where a missing/wrong secret shows up.
                raise RuntimeError(
                    f"node refused {path} (401 Unauthorized): pass --secret with the "
                    f"path to the node's .api_secret file")
            return e.code, None


def read_secret(path):
    path = os.path.expanduser(path)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return None


def check_node(node):
    code, status = node.get("/v1/status")
    if code != 200 or not status:
        raise RuntimeError(f"could not read /v1/status (HTTP {code}); is the node running?")
    synced = status.get("sync_status") == "no_sync"
    tip = status.get("tip", {})
    return {
        "name": "node_synced",
        "passed": synced,
        "sync_status": status.get("sync_status"),
        "height": tip.get("height"),
        "tip_hash": tip.get("last_block_pushed"),
        "node_reported_supply_epic": status.get("supply"),
        "user_agent": status.get("user_agent"),
    }


def check_supply_equation(node):
    code, _ = node.get("/v1/chain/validate", timeout=3600)
    return {
        "name": "supply_equation",
        "passed": code == 200,
        "http_status": code,
        "meaning": "node re-verified sum(unspent outputs) - sum(kernels) - offset*G "
                   "== scheduled issuance*H at its current tip",
    }


def check_schedule_vs_node(height, node_supply_epic):
    ours = scheduled_supply(height)
    return {
        "name": "schedule_matches_node",
        "passed": node_supply_epic == ours // EPIC_BASE,
        "height": height,
        "scheduled_supply": fmt(ours),
        "coins_on_chain_at_this_height": fmt(onchain_issued(height)),
        "note": "difference = miner contribution accrued since the last daily payout",
        "node_reported_whole_epic": node_supply_epic,
    }


def check_rollback(node):
    code, hdr = node.get(f"/v1/headers/{ROLLBACK_HEIGHT}")
    on_chain = []
    for h in REJECTED_HEADERS:
        c, _ = node.get(f"/v1/headers/{h}")
        if c == 200:
            on_chain.append(h)
    nxt_code, nxt = node.get(f"/v1/headers/{ROLLBACK_HEIGHT + 1}")
    nxt_hash = (nxt or {}).get("hash")
    passed = code == 200 and not on_chain and nxt_hash not in REJECTED_HEADERS
    return {
        "name": "rollback_2021",
        "passed": passed,
        "block_861141_hash": (hdr or {}).get("hash"),
        "block_861142_hash": nxt_hash,
        "rejected_headers_found_on_node": on_chain,
    }


def check_sync_log(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return {"name": "full_validation_at_sync", "passed": False, "error": f"log not found: {path}"}
    # All markers are written at Info level (chain/src/txhashset/txhashset.rs, chain/src/chain.rs),
    # so they survive file_log_level = "Info". "Finished validating..." is only logged after
    # Extension::validate(.., fast_validation=false) succeeds, which includes the supply equation.
    markers = {
        "rangeproofs": "Rangeproofs verification: processed",
        "kernel_signatures": "kernel signatures, pmmr size",
        "full_validation_finished": "Finished validating txhashset and rebuilding",
    }
    found = {k: None for k in markers}
    with open(path, errors="replace") as f:
        for line in f:
            for k, m in markers.items():
                if m in line:
                    found[k] = line.strip()[:200]
    return {
        "name": "full_validation_at_sync",
        "passed": all(found.values()),
        "evidence": found,
        "meaning": "the node's initial sync verified the supply equation, every unspent "
                   "output's range proof and every kernel signature (fast_validation=false)",
    }

# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Epic supply check (v1.1)")
    ap.add_argument("--node", default="http://127.0.0.1:3413")
    ap.add_argument("--secret", default="~/.epic/main/.api_secret",
                    help="path to the node's .api_secret file")
    ap.add_argument("--sync-log", help="path to epic-server.log from the node's initial sync")
    ap.add_argument("--schedule-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    results = [check_schedule()]
    if not a.schedule_only:
        try:
            secret = read_secret(a.secret)
            if secret is None:
                print(f"note: no API secret found at {a.secret}; owner-gated checks will fail "
                      f"unless the node runs without one", file=sys.stderr)
            node = Node(a.node, secret)
            n = check_node(node)
            results.append(n)
            if n["passed"]:
                results.append(check_supply_equation(node))
                results.append(check_schedule_vs_node(n["height"], n["node_reported_supply_epic"]))
                results.append(check_rollback(node))
            if a.sync_log:
                results.append(check_sync_log(a.sync_log))
        except (RuntimeError, urllib.error.URLError, OSError) as e:
            results.append({"name": "node", "passed": False, "error": str(e)})
            emit(results, a.json)
            return 2

    emit(results, a.json)
    return 0 if all(r["passed"] for r in results) else 1


def emit(results, as_json):
    if as_json:
        print(json.dumps(results, indent=2))
        return
    for r in results:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['name']}")
        for k, v in r.items():
            if k not in ("name", "passed"):
                print(f"         {k}: {v}")
    print("RESULT:", "ALL CHECKS PASSED" if all(r["passed"] for r in results) else "CHECK FAILED")


if __name__ == "__main__":
    sys.exit(main())
