# cake_mq tin_cap — experimental patch (on top of 720)

**Status: experimental, not for production.** Tested on one router model only.

- Patch: `729-net-sched-sch_cake-mq-tin-cap.patch`
- Requires: patch 720 (per-tin active share), see its README
- Default behaviour: **unchanged** (`tin_cap=0` = patch 720 as is)

---

## 1. What it fixes

With `tin_share=1` (patch 720), a priority tin concentrated on one cake_mq
instance gets its global threshold (Voice = rate / 4 in diffserv4). With 4
active instances, that equals the **whole rate of that instance**. A large
priority-marked flow then keeps priority up to the full instance rate, and
the lower tins **on the same instance** get almost nothing.

Measured (N5105, download, 2350 Mbit/s, diffserv4): a ping marked CS3
(Video tin), with an 800 Mbit/s CS4 flow placed on the same instance:

| Setup | Ping max |
|---|---|
| patch 720 (`tin_cap=0`) | **134–217 ms** |
| same flow unmarked (BE) | 2.8–3.7 ms |
| stock cake_mq (`tin_share=0`) | 2.2–2.9 ms |
| patch 729, `tin_cap=75` | **2.4–2.6 ms** |
| patch 729, `tin_cap=90` | **2.2–4.2 ms** |

Same queue and same CPU core in every row (even at 97–100 % CPU with an
unmarked flow): the cause is the per-instance priority, not the CPU.

## 2. How it works

`tin_cap` (debugfs `cake_mq/tin_cap`, percent, 0 = off): with `tin_share=1`,
the threshold of a **limited** tin (threshold below the full rate: Bulk,
Video, Voice in diffserv4) never exceeds `tin_cap` % of its instance's
rate. The full-rate (best effort) tin is left alone. Above the cap, the
priority tin loses priority but can still use idle bandwidth.

Takes effect at the next sync (200 µs), no restart needed:

```
echo 90 > /sys/kernel/debug/cake_mq/tin_cap
```

`cake_mq/stats` lines get `tin_capped` per tin appended (syncs where the cap
applied to that tin's threshold, not traffic actually held back); the
fields before it are unchanged.

## 3. Cost

Download, CS4 flows against 16 continuous Best Effort flows (same tests as
the 720 README):

| Test | Priority tin on | 720 | `tin_cap=90` | `tin_cap=75` |
|---|---|---|---|---|
| 1 CS4 flow | 1 instance | 537–550 | 487 (−10 %) | 400 (−26 %) |
| large + 3 × 2 Mbit/s CS4 | 1 instance | 530–540 + 6 | 470 + 6 (−12 %) | 398 + 6 (−26 %) |
| 4 CS4 flows | 3–4 instances | 522–555 | 522–526 (no change)* | 533 |

\* One more `tin_cap=90` run gave 613, with unusual activity counters;
three repeats in the same session (two at 90, one at 0) gave 522–526.

The cost only appears when a large priority flow shares its instance with
other traffic, which is exactly when the cap has to act. A priority flow
alone on its instance keeps the full instance rate (no competitor to lose
priority to). Small priority flows are not affected.

**Suggested setting:** `tin_cap=90` (protection with ~10 % cost in the worst
case measured). 75 gives the lower tins more room at a higher cost.

## 4. Known limitations

- One router model (N5105, i226, 4 queues), diffserv4, **download only**.
- The spike test forces the big flow onto the ping's instance by choosing
  the client port. Which instance a port maps to changes at every boot
  (random RSS key), and can change if the router's NAT remaps the port.
- A static cap: the real fix would give the instance carrying the priority
  tin a larger share of the global rate (demand-based rebalancing), which
  earlier experiments found hard to keep stable.
- Upload not measured with `tin_cap`.

## 5. Installation

Copy after patch 720 into `target/linux/generic/hack-6.12/` of an OpenWrt
25.12 buildroot. It applies only on top of 720.
