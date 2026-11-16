# Epic supply check: specification (v1.1)

**Purpose:** let anyone running an Epic node confirm, on their own machine, that the coins that exist match Epic's published emission schedule, with no data supplied by the Epic project.

**Script:** `supply_check.py` (Python 3.8+, standard library only).

**Source reference:** github.com/EpicCash/epic, tag v4.1.2, commit `bd3a8c8c5e957e57574364326dfb17051d0096ae`.

## 1. What has to be true, and how each part is checked

In Mimblewimble, the total supply is proven by two facts together:

1. **The supply equation:** the sum of all unspent coin commitments, minus the sum of all kernel excesses and the kernel offset, equals the total issued times the value generator H.
2. **Range proofs:** every unspent coin carries a valid range proof, so no hidden negative amount can make the equation balance while coins are actually being created.

The 2021 incident was a failure of the second fact, so the check covers both.

| # | Check | How | Independent of Epic project data? |
|---|---|---|---|
| 1 | Schedule | Recompute the emission schedule and miner contribution from the published rules. The results must be a maximum supply of 20,999,879.72668800 EPIC and a lifetime contribution of 1,280,478.24 EPIC. | Yes: pure arithmetic |
| 2 | Node synced | `GET /v1/status`: `sync_status` must be `no_sync`; read the tip height. | Your node |
| 3 | Supply equation | `GET /v1/chain/validate`. The node re-runs the supply equation over its full unspent-output and kernel sets at the tip (`Extension::validate`, fast mode). | Your node, public code |
| 4 | Schedule = node | The independently computed scheduled supply at the tip must equal the node's figure. The script also prints the exact number of coins on chain (section 3). | Yes |
| 5 | 2021 rollback | The header at 861,141 exists; the two rejected header hashes are unknown to the node; the header at 861,142 is not one of them. | Your node |
| 6 | Range proofs and signatures | From the node's log: its initial sync ran full validation (`fast_validation = false`), covering every range proof, every kernel signature and the supply equation. After sync, every new block is fully validated on arrival. | Your node's log |

## 2. Why not use the node's own supply number

The `supply` field in `/v1/status` is calculated from the schedule, not measured, and `max_supply` is hardcoded to 21,000,000 (`api/src/handlers/server_api.rs:63-64`). Check 4 uses it only as a cross-check of the arithmetic. The measurement is check 3.

## 3. Coins on chain vs. scheduled supply

The miner contribution is paid once every 1,440 blocks, covering the previous 1,440 blocks (`add_reward_foundation` in `consensus.rs`). Between payouts, the coins on chain therefore trail the schedule by the contribution accrued since the last payout: at most one day's contribution, now about 16 EPIC.

The supply equation the node checks uses the on-chain figure (`total_overage_at_height`). The script reproduces that figure exactly.

## 4. Running it

1. Use a node running v4.1.2 or later.
2. For check 6, sync the node from scratch (empty `chain_data`) and keep the log from that sync. Logs rotate, so copy `epic-server.log` as soon as the sync finishes, or raise `log_max_size` first. The markers the script looks for are logged at Info level.
3. Wait until the node is fully synced.
4. Run:
   ```
   python3 supply_check.py --secret ~/.epic/main/.api_secret --sync-log /path/to/epic-server.log
   ```

Notes:

- Check 3 can take several minutes on a full chain and briefly holds the chain lock, so block processing pauses while it runs. Run it on a node you control, not a public seed.
- `--schedule-only` runs check 1 without a node.
- `--json` gives machine-readable output.
- Exit codes: 0 = all checks passed, 1 = a check failed, 2 = the script could not run (including a missing or wrong `--secret`, reported as 401 Unauthorized). `/v1/status` is public on most nodes; the password is first needed at `/v1/chain/validate`.

## 5. Example output (real node, v4.1.2 synced from scratch, 2026-11-17)

```
[PASS] schedule
         max_supply: 20,999,879.72668800 EPIC
         miner_contribution_total: 1,280,478.24000000 EPIC
         miner_contribution_share_of_supply: 6.10%
         miner_contribution_last_block: 4377600
[PASS] node_synced
         sync_status: no_sync
         height: 3802013
         tip_hash: cb8ca92ae533382739f17b0c9addf01b700103349ead4019c0ed648379c1db4a
         node_reported_supply_epic: 19502333
         user_agent: MW/Epic 4.1.2
[PASS] supply_equation
         http_status: 200
[PASS] schedule_matches_node
         height: 3802013
         scheduled_supply: 19,502,333.00000000 EPIC
         coins_on_chain_at_this_height: 19,502,328.41570000 EPIC
         node_reported_whole_epic: 19502333
[PASS] rollback_2021
         block_861141_hash: a7ebf4940531109d4cebec892fc65c196d3a38d617e5587c4837c16cee1fa215
         block_861142_hash: 5cf4a44584399abf23b26aa457d8817a122efab0c1127096cadcbe5f626876af
         rejected_headers_found_on_node: []
[PASS] full_validation_at_sync
         rangeproofs: "Rangeproofs verification: processed 119277 proofs out of 119277 total rangeproofs"
         kernel_signatures: "verified 4149407 kernel signatures, pmmr size 8298800, took 238s"
         full_validation_finished: "Finished validating txhashset and rebuilding. Going to replace..."
RESULT: ALL CHECKS PASSED
```

The full check took 1 minute 35 seconds. The tip was 413 blocks past the last daily miner-contribution payout, so the coins on chain trail the schedule by 413 × 0.0111 = 4.5843 EPIC: exactly the difference shown.

## 6. Limits

- **Checks 3 and 6 rely on the node software doing what its public source says.** That is the same trust anyone places in the reference implementation, and the code is open to inspection. A fully separate implementation of the commitment sum is possible in a later version, but kernels are hard to fetch: `get_last_n_kernels` has no paging, so they would have to be pulled all at once or read from the node's data files.
- **A fast-synced node does not replay old blocks, and does not need to.** The supply equation and range proofs are checked on the complete current coin and kernel set, which covers all of history in aggregate.
- **Individual amounts stay private.** Only totals are verified.
