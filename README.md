# Epic Private Internet Cash: Supply and Distribution Statement

This is a factual statement of how EPIC is issued, where every coin came from, and how anyone can verify the supply independently. It is written for exchange technical reviewers, researchers and holders. Every figure below can be checked against the public source code at the commit listed under [Sources](#sources). The check script is in this repository: [`verify/supply_check.py`](verify/supply_check.py).

This document was drafted by Epic community volunteer contributors.

## Key facts

- Every EPIC was created by proof-of-work mining. Supply started at zero, just like Bitcoin's. There was no premine, presale, ICO, investor allocation or team allocation.
- Total supply is capped at **20,999,879.73 EPIC**, reached gradually through block rewards that halve on a fixed schedule. It is often rounded to 21 million.
- Until about the start of 2028, a declining share of each block reward, the **miner contribution**, pays for the project's costs. It creates no extra coins. It is now 1.11%, and it ends permanently after block 4,377,600.
- In March 2021, a flaw inherited from Grin's code was exploited on Grin, MWC and Epic. Epic fixed the flaw, rolled the chain back to block 861,141 (the last valid block), and permanently rejects the invalid blocks. No counterfeit coins exist on today's chain.
- Anyone running an Epic node can verify that the total supply matches the schedule exactly, using the check described in [section 6](#6-how-to-verify-the-supply-yourself).

## 1. Every EPIC was mined

Epic's supply started at zero. The genesis block paid no reward, and every coin since has been created in a block found by proof-of-work mining. Epic's 2019 whitepaper said so before launch, and it remains true: *"Every Epic is mined into existence via proof of work."*

## 2. Emission schedule

Epic targets one block per minute (1,440 blocks per day). The block reward follows a fixed schedule set in the node software (`core/src/consensus.rs`). It cannot be changed without a change that every node operator would have to adopt.

| Era | Block heights | Reward per block | EPIC created in era | Cumulative supply |
|---|---|---|---|---|
| 1 | 1 – 480,960 | 16 EPIC | 7,695,360 | 7,695,360 |
| 2 | 480,961 – 1,157,760 | 8 EPIC | 5,414,400 | 13,109,760 |
| 3 | 1,157,761 – 2,023,200 | 4 EPIC | 3,461,760 | 16,571,520 |
| 4 | 2,023,201 – 3,175,200 | 2 EPIC | 2,304,000 | 18,875,520 |
| 5 | 3,175,201 – 4,642,560 | 1 EPIC | 1,467,360 | 20,342,880 |
| 6+ | from 4,642,561 | 0.15625 EPIC, halving every 2,102,400 blocks (about 4 years) | about 657,000 | 20,999,879.73 |

The final halving brings the reward to zero around block 55.1 million. The exact maximum supply, summed from the schedule, is **20,999,879.72668800 EPIC**.

The node's `/v1/status` endpoint reports a supply figure calculated from this schedule, and a rounded maximum of 21,000,000. That figure is a convenience display, not a measurement. [Section 6](#6-how-to-verify-the-supply-yourself) describes the actual check.

## 3. Miner contribution (called the "foundation levy" in the code)

A new currency with no outside funding still has costs before it has any value: servers and seed nodes, software development, and making the world aware it exists. Epic's miners carried those costs themselves. From launch until about the start of 2028, a fixed, declining share of each block reward goes to the project's costs instead of to the miner who found the block. The 2019 whitepaper called these "mining contributions", and today's schedule is exactly the one it published before launch.

| Period | Block heights | Share of block reward | Approx. EPIC in period |
|---|---|---|---|
| Launch – end 2019 | 1 – 172,800 | 8.88% | 245,514 |
| 2020 | 172,801 – 698,400 | 7.77% | 518,265 |
| 2021 | 698,401 – 1,224,000 | 6.66% | 262,393 |
| 2022 | 1,224,001 – 1,749,600 | 5.55% | 116,683 |
| 2023 | 1,749,601 – 2,275,200 | 4.44% | 70,969 |
| 2024 | 2,275,201 – 2,800,800 | 3.33% | 35,005 |
| 2025 | 2,800,801 – 3,326,400 | 2.22% | 19,980 |
| 2026 | 3,326,401 – 3,852,000 | 1.11% | 5,834 |
| 2027 | 3,852,001 – 4,377,600 | 1.11% | 5,834 |
| From block 4,377,601 | — | 0% | 0 |
| **Total** | | | **1,280,478 (6.1% of total supply)** |

Calendar years are approximate, assuming one block per minute from launch. Block heights are exact (`core/src/consensus.rs`, `FOUNDATION_LEVY`).

The contribution creates no extra coins. It comes out of the reward miners would otherwise receive, so total supply is the same with or without it. It is now 1.11%, about 16 EPIC per day, and it ends permanently after block 4,377,600. Epic has no founder or investor allocation of any kind.

The schedule is fixed in the node software. The software contains one pre-built payout for each day (`debian/foundation.json`, 3,040 entries), and every node rejects a block that is missing the scheduled one. No one can raise, extend or redirect the contribution without a change that every node operator would have to adopt.

## 4. Why there is no foundation

The 2019 whitepaper planned an "EPIC Blockchain Foundation" to receive these contributions, with a decentralized organization to take over later. Neither was formed, by choice. In open-source projects, any central place where money sits, or where money decisions are made, attracts conflict: competing claims, resentment and attempts at capture. Rather than build that target, the contributions have been held only by individuals working on Epic, never by a company or foundation. Since 2023 they have been held by an independent developer. They have paid for development, infrastructure and awareness.

Because there is no foundation or treasury, there is no central set of books for these funds. What the protocol guarantees, and what anyone can verify, is everything that bears on supply: the amount of each contribution, the schedule and the end date.

## 5. The March 2021 incident

In March 2021, a flaw in range-proof verification inherited from Grin's code was exploited on Grin, MWC and Epic. Range proofs are what stop a Mimblewimble transaction from hiding a negative amount. Nodes cached verification results in a way that let a proof already checked once be reused on a different output. On Epic, this allowed counterfeit coins to be created. The flaw was detected the same day.

- **March 18, 2021:** release 2.13.0 removed the faulty cache, so every range proof is fully verified in every block. Grin removed the same cache on the same day.
- **April 5, 2021:** release 2.15.0 rolled the chain back to block 861,141, the last valid block, and made every node permanently reject the invalid blocks that followed it. The rebuilt chain data was published so every node could restart from the same valid state.

About 2.8 million counterfeit coins reached ViteX, a decentralized exchange on the separate Vite blockchain, before trading stopped on March 20, 2021. The rollback removed the counterfeit coins from Epic's chain. It could not reverse trades already settled on ViteX. As with Bitcoin's 2010 value-overflow incident, the fix was a corrected rule plus a return to the last valid chain. No counterfeit coins exist on today's chain, and the check in section 6 lets anyone confirm that.

Afterwards, a volunteer group calling itself Epicenter DAO announced a plan to reimburse affected ViteX buyers with an IOU token, to be paid from the fees of an organization it intended to form. Its announcement described the effort as volunteer-led and stated that it created no liability. That organization was never formed and never earned fees, and no reimbursements were paid.

## 6. How to verify the supply yourself

Mimblewimble hides individual amounts, but it lets anyone check the total supply with arithmetic. Every coin is a cryptographic commitment. If the sum of all unspent coins, minus the sum of all transaction kernels, equals the total block rewards issued so far, then no coins exist beyond the schedule. A range proof on every coin rules out hidden negative amounts.

Every Epic node performs this full check when it first syncs, covering every range proof, every kernel signature and the supply equation. It then checks every new block as it arrives. The script in this repository, [`verify/supply_check.py`](verify/supply_check.py), lets anyone confirm all of this on their own node. It:

- recomputes the emission schedule and the miner contribution from the published rules;
- asks your node to re-verify the supply equation at the current block;
- confirms from your node's log that its initial sync completed the full range-proof and signature check;
- confirms that the chain continues from block 861,141 and that the blocks rejected in 2021 are not on it.

The script uses only your own node and the public code. It relies on no data supplied by the Epic project. The miner contribution is paid once a day, so the coins on chain at a given block can trail the schedule by up to one day's contribution (currently about 16 EPIC). The script reports the exact figure.

Quick start (Python 3.8+, no extra packages):

```
python3 verify/supply_check.py --schedule-only
python3 verify/supply_check.py --secret ~/.epic/main/.api_secret --sync-log /path/to/epic-server.log
```

Full details, expected output and limits are in [`verify/SPEC.md`](verify/SPEC.md).

## 7. Limits of what can be verified

- Individual balances and transaction amounts are private by design. The supply is verified as a total, not by reading balances.
- Spending of miner contribution funds happens in ordinary private transactions and cannot be traced on-chain.

## Sources

- Epic node source: [github.com/EpicCash/epic](https://github.com/EpicCash/epic), tag v4.1.2, commit `bd3a8c8c5e957e57574364326dfb17051d0096ae`.
  - Emission: `core/src/consensus.rs` lines 41–80.
  - Miner contribution: `core/src/consensus.rs` lines 186–298 and `debian/foundation.json` (sha256 `5a3a7584127dd31fba18eaeff1c551bfaa74b4e50e537a1e1904fe6730b17f5c`).
  - Enforcement: `core/src/core/block.rs` lines 889–897.
  - Bad-block rejection: `chain/src/pipe.rs` lines 720–730.
- 2021 releases: tags `debian/2.13.0-1` (commit `b4a323a`, "Remove cache on kernel and output validation") and `debian/2.15.0-1`.
- Epic Cash whitepaper v7.1b (2019), section "Mining Contributions", p. 15.
- Grin: [forum.grin.mw, March 2021 incident thread](https://forum.grin.mw/t/resolved-do-not-use-grin-grin-wallet-grin-ironbelly-until-further-notice/8620); mimblewimble/grin commit `87ff219d` (#3597).
- MWC: [forum.mwc.mw/t/critical-bug-report/102](https://forum.mwc.mw/t/critical-bug-report/102).
- Epicenter DAO, ["Epicenter IOU and ViteX Claim Form"](https://medium.com/epic-cash/epicenter-iou-and-vitex-claim-form-59432315668b), Medium, April 13, 2021.
