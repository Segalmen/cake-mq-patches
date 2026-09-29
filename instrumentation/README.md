# cake_mq sync instrumentation (712, 713, 714)

Measurement tool for the cake_mq sync logic, as described in my post #248
of the OpenWrt forum thread "Cake-mq - backport of multi-core capable CAKE
implementation to 25.12 branch".

**Status: experimental, for measurement only.** With all knobs at their
default values, the code behaves exactly as upstream cake_mq.

## Base and order

Apply on top of OpenWrt 25.12 (kernel 6.12 cake_mq backport), in this order:

1. `701-03` (backport of a3729e0df005, skip clearing unused tins)
2. `710` (sync_time via debugfs, from OpenWrt main `hack-6.12`, not included here)
3. `712-net-sched-sch_cake-mq-demand-rebalance.patch`
4. `713-net-sched-sch_cake-mq-sync-stats.patch`
5. `714-net-sched-sch_cake-mq-tuning-knobs.patch`

They build on each other and on 710's `cake_mq` debugfs directory.

This stack is **separate** from patches 720/729 in `../patches/`, which apply
directly on 25.12 without 710 and create the debugfs directory themselves:
do not combine the two stacks.

## Read-only counters: `/sys/kernel/debug/cake_mq/stats`

Split egress / ingress:

- `syncs`: number of sync events
- `nact` histogram (1..8 active queues) and `nact_changes`: how often the
  active-queue count changes between two syncs
- `saturated`: instance shaper-limited at sync time
- `rate_kbs_sum`: sum of applied local rates (gives the average local rate)
- `overcommit`: syncs where own new rate + last published rates of the other
  active instances > global rate, plus the excess

Take a snapshot before and after a run and compute the deltas.

## Runtime knobs (defaults = upstream)

| Knob | Default | Meaning |
|---|---|---|
| `rebalance` | 0 | 0 = upstream equal split; 1 = v1, 2 = v2 (experimental redistribution, see below) |
| `active_hold` | 0 | 0 = upstream activity test; N = an instance counts as active if it sent within the last N × sync_time (debounce) |
| `ewma_shift` | 2 | smoothing of the served rate |
| `v1_headroom_shift` | 2 | v1 tuning |
| `v1_sat_shift` | 3 | v1 tuning |
| `v2_spare_pct` | 100 | v2 tuning |

- **v1**: light instances capped at their served rate + headroom, saturated
  ones share the rest.
- **v2**: never below the equal share; saturated instances also get the unused
  part of the equal share of the non-saturated ones.

Implementation: lockless, same `READ_ONCE`/`WRITE_ONCE` pattern as the
upstream sync code; counters are `atomic64` per direction.

## Main results (post #248, N5105 / i226, 4 queues)

- Upstream overcommits in about 25 % of syncs (mean excess 57–70 Mbit/s).
- `active_hold` reduces it monotonically: 0 → 4 → 8 → 16 gives egress
  overcommit 26 % → 6–9 % → 3 % → 0.6 %, with no visible cost in those tests.
- v1 under-allocates with bursty traffic; v2 overcommits more and showed higher
  latency peaks.

One box, one or two runs per setting, browser-based load at 1200 Mbit/s:
see the post for the full tables and caveats.

## Where this led

The debounce idea was carried over, per tin, into patch 720 (per-tin active
share), and 729 (`tin_cap`) was added on top: see `../README.md`.
