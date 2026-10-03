# cake_mq per-tin active share — experimental patch

**Status: experimental, not for production.** Tested on one router model only.
Feedback and measurements from other hardware are welcome.

- Patch: `720-net-sched-sch_cake-mq-per-tin-active-share.patch`
- Target: OpenWrt 25.12 (kernel 6.12 with the cake_mq backport)
- Default behaviour: **unchanged** — nothing happens until you enable it

> **Update (2026-10-03).** Measured after this README was written; the text
> below is kept as originally published.
> - **Upload** (1 priority flow vs 16 Best Effort flows, CS4, diffserv4, same
>   router, measured 2026-09-28), plain cake / stock cake_mq / this patch,
>   Mbit/s: 1 flow 501 / 124 / 536 ; 4 flows 546 / 265 / 536 ;
>   1 large + 3 × 2 Mbit/s 485 / 120 / 529. This patch is within −2 % to +9 %
>   of plain cake. Single runs, except plain cake for 1 flow and for
>   large + small (3 runs each, averaged).
> - **diffserv3 and diffserv8**: this patch restores the priority flow in both
>   modes (results in the 729 README, section 4). In diffserv3 the priority
>   flow must be EF: CS4 maps to Best Effort.
> - **Bursty traffic**, latency only: `active_hold` 0 vs 8 showed no difference
>   in ping latency (5 runs each); the spikes seen in those runs depended on
>   flow placement and led to patch 729. Rate over-commit (section 1) was not
>   re-measured.
> - All tests used CUBIC; BBR was not tested.

---

## 1. What it fixes

With cake_mq, the global rate is split between one CAKE instance per
hardware queue. At every sync, each instance also recomputes its
**DiffServ tin thresholds** from its local share. A priority flow (EF,
CS5, CS4 — e.g. interactive or real-time traffic) that lands on a single instance only gets
a fraction of the priority it would get with plain cake.

Measured with this patch on the test bench (download, 2350 Mbit/s,
diffserv4, CS5-marked flows against 16 Best Effort flows; plain cake and
cake_mq measured the same day, same conditions). Values in Mbit/s,
priority / Best Effort:

| Scenario | plain cake | cake_mq, `tin_share=0` (upstream) | cake_mq, `tin_share=1` |
|---|---|---|---|
| 1 priority flow | 550 / 1669 | 135 / 2072 (−75 %) | **545 / 1646** |
| 4 priority flows | 555 / 1658 | 403 / 1786 (−27 %) | **539 / 1659** |
| large + 3 × 2 Mbit/s priority | 530 + 6 / 1685 | 130 + 6 / 2067 | **536 + 6 / 1650** |

With `tin_share=1`, each tin's global share is divided by the number of
instances **recently active in that tin** (a packet of that tin dequeued
within the last `tin_hold` × sync_time), instead of by the number of
globally active instances. **The per-instance hard-shaper allocation is
unchanged; the patch only changes per-tin thresholds.**

**Placement matters much less.** With `tin_share=0`, priority throughput
is roughly "instances carrying the tin × local tin threshold": about 135
on one instance, 273 on two, 403 on three (local Voice threshold
≈ 147 Mbit/s). With `tin_share=1`, priority throughput stays close to
plain cake whatever the placement, with a small cost when the priority
tin is spread over many instances (each priority flow is then capped by
its own instance's share of the tin threshold):

| Priority tin carried by | Priority throughput (plain cake: 550–555) | Gap |
|---|---|---|
| 1 instance  | 537–550 | 0 to −2 % |
| 2 instances | 536–554 | 0 to −3 % |
| 3 instances | 529–539 | −3 to −5 % |
| 4 instances | 522     | −6 % |

With 4 instances, upstream cake_mq ends up with the same per-instance
threshold in theory (this case was not measured with `tin_share=0`).

**Sparse priority traffic does not steal the share.** In the "large +
small" scenario, per-instance `tc` counters showed the small flows on
another instance than the large one, yet the average number of instances
seen active in the priority tin stayed at 1.01–1.02: at 2 Mbit/s, packets
are too far apart to keep the tin active within the hold window, and the
large flow is not penalised. (Earlier experimental runs with medium
flows, 3 × 20 Mbit/s, counted them part of the time; priority traffic
then got ~3 % more than plain cake.)

**Real classification path.** The same results were obtained with the
priority flows marked CS4 instead of CS5, and with a QoS
script's full ingress path (DSCP restored by `act_ctinfo`, cake_mq and
all settings applied by the script): 1 CS4 flow 537 (−2 %), large +
3 × 2 Mbit/s CS4 540 + 6 (+2 %).

**`active_hold`:** 0, 8 and 16 gave the same results within ±3 % in these
continuous iperf3 tests, with `tin_share` on or off: the instances stay
active all the time, so there is nothing to smooth. In earlier bursty
real-traffic tests (browser speed test, experimental patch stack) a hold
of 8–16 cut rate over-commit by a factor of 10–25; that case has not been
re-measured with this patch.

---

## 2. Installation

This is a kernel patch: it cannot be installed with `apk`. You need your
own OpenWrt 25.12 build.

1. Copy the patch into your buildroot:
   ```
   cp 720-net-sched-sch_cake-mq-per-tin-active-share.patch \
      openwrt/target/linux/generic/hack-6.12/
   ```
2. Check that it applies:
   ```
   make target/linux/{clean,prepare} V=s 2>&1 | grep -E 'Applying.*720-|FAILED|\.rej'
   ```
   Expected: an `Applying …720-…` line, no `FAILED`, no `.rej`.
3. Build and flash your image as usual.
4. After boot, the knobs appear in `/sys/kernel/debug/cake_mq/`.

It applies on the stock 25.12 cake_mq code, with or without the upstream
fix `sch_cake: skip clearing unused tins during rate adjustment`.

**Not compatible** with the author's experimental 710–717 patch stack
(same debugfs directory): use one or the other.

---

## 3. Runtime knobs

All in `/sys/kernel/debug/cake_mq/`, changeable at any time with `echo`:

| Knob | Default | Meaning |
|---|---|---|
| `tin_share` | 0 | 0 = upstream; **1 = per-tin active share** |
| `tin_hold` | 8 | a tin stays "active" on an instance for N × sync_time (200 µs) after its last packet |
| `active_hold` | 0 | 0 = upstream activity test; N = an instance stays active for N × sync_time after its last packet |
| `stats` | — | read: counters; write anything: reset |

Suggested settings. `tin_share=1` is what matters. `active_hold` made no
difference in continuous tests; `active_hold=8` is used here as a
conservative starting point for bursty traffic, based on earlier
experimental-stack measurements (bursty traffic has not yet been re-tested
with this patch):
```
cd /sys/kernel/debug/cake_mq
echo 8 > active_hold
echo 8 > tin_hold
echo 1 > tin_share
```

These settings are **lost on reboot**: apply them from a boot script
(e.g. `/etc/rc.local`) if you want them permanent.

---

## 4. Checking that it works

```
echo reset > /sys/kernel/debug/cake_mq/stats
# ... run your test ...
cat /sys/kernel/debug/cake_mq/stats
```

For each direction: `syncs` and `tin_nact_sum` per tin (internal tin
order). `tin_nact_sum / syncs` = average number of instances seen active
in that tin. With one priority flow, the priority tin should be close to 1.

Internal tin order: diffserv8 = same as `tc -s` (Tin 0 … 7);
diffserv4 = Best Effort, Bulk, Video, Voice.

---

## 5. System setup matters

On the test router (Intel N5105, i226), cake_mq only behaved reliably
with:

- **RPS disabled** on the WAN interface;
- **one NIC queue per CPU core**, pinned, with **irqbalance stopped**.
  With irqbalance running, two busy RX queues sometimes ended up on the
  same core: that core hit 100 %, cake was starved and throughput fell by
  ~25 % (about one run in four).

Example for a 4-queue NIC (IRQ numbers from `grep eth1- /proc/interrupts`):
```
/etc/init.d/irqbalance stop
echo 0 > /proc/irq/<irq of eth1-TxRx-0>/smp_affinity_list
echo 1 > /proc/irq/<irq of eth1-TxRx-1>/smp_affinity_list
echo 2 > /proc/irq/<irq of eth1-TxRx-2>/smp_affinity_list
echo 3 > /proc/irq/<irq of eth1-TxRx-3>/smp_affinity_list
```

On stronger CPUs this may matter less; on a single-queue NIC or a
single-core router, cake_mq brings nothing over plain cake.

---

## 6. Known limitations

- Validated with this patch on **one** router model (Intel N5105, i226,
  4 queues), **diffserv4**, **download only**, iperf3 load (CS5-marked
  flows against Best Effort), one queue per core, irqbalance stopped.
- diffserv8 was only measured with the experimental stack (same
  algorithm), not yet with this patch.
- `active_hold` on bursty real traffic not re-measured with this patch.
- Priority traffic was placed on 1 to 4 instances and Best Effort on 3 to
  4 instances in the validation runs. The more instances carry the
  priority tin, the larger the gap with plain cake (up to −6 % on 4
  instances, see section 1). Real multi-server traffic (fast.com,
  30 connections, browser and CLI LibreQoS tests) spread over 4 instances
  with no added latency, but browser tests do not reach the shaper limit.
- A tin can never exceed the local share of the instance carrying it
  (global rate / active instances). In diffserv8, where the priority tin
  threshold (~45 % of the rate) is close to a 2-instance share, a priority
  flow sharing its instance with other traffic can stay below plain cake.
- Tin activity is based on recent dequeues only, not on per-tin backlog.
- Sparse priority traffic (a few Mbit/s) is naturally ignored by the
  activity window; medium flows (tens of Mbit/s) are counted part of the
  time and may give priority traffic a few percent more than plain cake.
- `autorate-ingress` is not supported by cake_mq itself.

---

## 7. Feedback

Useful reports include: router model, CPU, NIC and queue count, line
rate, diffserv mode, results with `tin_share=0` vs `tin_share=1` (same
test, same conditions), and the `stats` output.
