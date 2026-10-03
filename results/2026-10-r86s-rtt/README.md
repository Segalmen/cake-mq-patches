# cake_mq vs plain CAKE on an 8-core router: the `rtt` setting matters

**Short version.** On an R86S (Intel i3-N305, 8 cores) with a 10 Gbit/s line, `cake_mq` loses 10-15 % of
multi-flow upload throughput compared with plain `cake` **when CAKE's `rtt` is set to 10 ms**. With `rtt 30ms`
or `rtt 100ms` (the CAKE default), the loss disappears. Plain `cake` is not affected by `rtt` in these tests.
Single-flow throughput is the same in every case. sqm-scripts users who keep the default options are not affected.

## Setup
- Router: R86S, Intel i3-N305 (8 cores), OpenWrt 25.12.5 with the `cake_mq` backport. The kernel also carries
  private experimental debugfs knobs; **all were set to 0** (original `cake_mq` decisions) and checked in every run.
- Line: Init7 10 Gbit/s. Server: Init7 public iperf3 server, about 5-6 ms away.
- Shaper: 8500 Mbit/s in both directions. Only the **upload** direction was measured.
- Shaping by **sqm-scripts 1.7.2** (`layer_cake.qos`, files checked identical to tag v1.7.2 by sha256);
  `use_mq=0` gives `cake`, `use_mq=1` gives `cake_mq` (and an IFB with 8 queues). No other QoS script was running.
- Load 1: one TCP flow (30 s). Load 2: 12 TCP flows (3 x `-P 4`, 40 s). `iperf3 -C cubic`. Throughput = mean of
  1-s intervals inside a fixed window.

## Method
- One parameter changed per series; every series was **written down before its first run** (question, order, rule).
- Each run records the exact `tc` options on both qdiscs; a run counts only if all of them match and every iperf3
  process succeeded. Failed runs are never replaced.
- Comparison rule for cake_mq (M) vs cake (S), 3 alternated pairs: **LOSS** if M <= 0.90 x S in all 3 pairs,
  **GAIN** if M >= 1.10 x S in all 3, otherwise **no clear difference**. Ratios are always reported.

## Results (12 flows, ratio cake_mq / cake per pair)
| Series | Options (same in both arms) | cake_mq / cake | Rule verdict |
|---|---|---|---|
| B1 | sqm defaults (`diffserv3`, `rtt 100ms`...) | 1.001 / 1.002 / 0.999 | inconclusive (one run failed: server) |
| B2 | `diffserv4 dual-srchost no-split-gso rtt 10ms memlimit 128mb` | 0.853 / 0.925 / 0.886 | no clear difference |
| B3 | B2 + `split-gso` (egress) | 0.949 / 0.957 / 0.998 | no clear difference |
| B4 | B2 + `rtt 100ms` (egress) | 1.000 / 0.998 / 1.000 | no clear difference |
| B5 | B2 + automatic `memlimit` (egress) | 0.913 / 0.872 / 0.872 | no clear difference |
| B6 | B2 + `triple-isolate` (egress) | 0.872 / 0.885 / 0.869 | **LOSS** |
| B7 | B2 + `diffserv3` (egress) | 0.848 / 0.861 / 0.899 | **LOSS** |
| B8 | B2 without `ingress` on the IFB | 0.905 / 0.901 / 0.899 | no clear difference |

Plain `cake` stayed at about 8.0-8.1 Gbit/s in every series, whatever the options.

**Confirmation within cake_mq only (B4C)**, egress `rtt 10ms` vs `rtt 100ms`, 5 alternated pairs:
6.79-7.32 vs 8.12-8.13 Gbit/s, ratio 0.891 / 0.858 / 0.836 / 0.901 / 0.871 (median 0.871): **confirmed**.

**rtt 10 / 30 / 100 ms within cake_mq (RTT3)**, 5 rotated rounds: 30 ms gives 8.08-8.10 Gbit/s, i.e.
0.994-0.996 of the 100 ms value; 10 ms gives 0.84-0.91. Formally **inconclusive** (one run failed: server busy),
but the pattern is the same in all rounds.

Single flow (load 1): no difference in any series. No CPU core saturated (max about 56 %). Ping p99 about 5-6 ms
in both modes (not a dedicated latency study).

## What this shows, and what it does not
- **Shown (this router, these options, upload):** with `cake_mq`, a 10 ms `rtt` costs about 13 % of multi-flow
  throughput; 30 ms already avoids it. Among the six options that differed from sqm defaults, only `rtt` mattered;
  `split-gso` reduced the loss somewhat; `memlimit`, flow isolation, `diffserv` and the IFB `ingress` keyword did not.
- **Not shown:** why. A plausible explanation (not verified): each instance shapes only a fraction of the rate, and
  a short `rtt` makes each instance's AQM too aggressive. Download direction, other hardware and other rates were
  not tested.

## Practical advice
If you enable `use_mq` (or `cake_mq` in any script) and you lowered CAKE's `rtt` below its default (for example to reduce latency), use **30 ms or more**.
With the defaults (`rtt 100ms`), nothing to change.

## Files
- `scripts/bench-functions.sh`: the measurement functions (`run13`: cake vs cake_mq; `run14`: rtt 10 vs 100;
  `run15`: rtt 10/30/100). Router address, sqm section and server are hard-coded: adapt before use.
- `scripts/*.py`, `scripts/axisB-option-check.sh`: analysis and validity checks.
- `data/r86s-2026-10-cake-vs-cake_mq.tar.xz`: raw iperf3 JSON, ping, CPU and state records of every run. In the state
  records, the line ending in `_nft=absent` confirms that no other QoS script's nftables table was loaded.
