# Testing guide

Thank you for testing. Both knobs are off by default, so an image built
with the patches behaves like stock OpenWrt until you enable them.

## 1. Requirements

- OpenWrt 25.12 built from source, with patches 720 (and 729) in
  `target/linux/generic/hack-6.12/`
- a router with a multi-queue NIC and at least 2 CPU cores
- cake_mq in use (SQM with `use_mq`, or your own script)
- iperf3 on a client and on a server on the other side of the router

Check after boot:

```
ls /sys/kernel/debug/cake_mq/        # tin_share, tin_hold, active_hold, tin_cap, stats
tc qdisc show | grep -c 'qdisc cake 0'   # number of cake_mq instances
```

## 2. Test 1: priority share (patch 720)

Measure how much a single priority-marked flow gets against bulk traffic,
with `tin_share=0` (stock) then `1`, same test, same conditions.

**Upload** is the easiest: the marking set by the client reaches the
router egress unchanged.

```
# on the router, before each run
echo 0 > /sys/kernel/debug/cake_mq/tin_share     # then 1 for the second run
echo reset > /sys/kernel/debug/cake_mq/stats

# on the client: 1 CS4 flow + 16 best effort flows, 30 s, at the same time
iperf3 -c SERVER -p 5201 -t 30 -S 0x80 &
iperf3 -c SERVER -p 5202 -t 30 -P 16
```

Download works too if the DSCP marking survives the path from the
server (for example on a local bench). Over the Internet it usually does
not.

Expected: with `tin_share=0` the CS4 flow gets roughly a quarter of what
it gets with plain cake; with `tin_share=1` it should be close to plain
cake. Please also run plain cake once as a reference if you can.

## 3. Test 2: tin_cap (patch 729, advanced)

The effect only shows when a large priority flow (above the per-instance
share, i.e. rate / number of instances) lands on the same cake_mq
instance as lower-priority latency-sensitive traffic. Placement follows
the flow hash, so you may need several runs:

- run a ping to the server, marked in a lower tin (e.g. `ping -Q 0x60`
  for CS3 / Video), plus a large CS4 flow above the per-instance share;
- find which instance carries each (`tc -s qdisc show dev <iface>`,
  per-instance tin counters);
- compare the ping with `tin_cap=0` and `tin_cap=90`, in runs where both
  share an instance.

## 4. What to report

Please open an issue with:

- router model, CPU and core count, NIC and number of queues
- OpenWrt version, line rate / shaper rate, diffserv mode, direction
- results with the knob off and on (same test), and plain cake if run
- `cat /sys/kernel/debug/cake_mq/stats` after each run
- anything odd: throughput drops, latency spikes, CPU at 100 %

Negative results are just as useful as positive ones.

## 5. Optional: choosing the instance a flow lands on

With few flows, the hash decides which cake_mq instance carries each flow, so two
runs of the same test can occupy different instances. On some routers the placement
can be predicted and chosen. This depends on the router setup: verify it before use.

1. On the LAN-side interface (where the test traffic enters), read the RSS setup:
   `ethtool -x <lan-if>` (indirection table, key, hash function) and
   `ethtool -n <lan-if> rx-flow-hash tcp4` (hashed fields).
2. Read the steering setup: RPS (`/sys/class/net/<lan-if>/queues/rx-*/rps_cpus`),
   XPS on the WAN interface (`/sys/class/net/<wan-if>/queues/tx-*/xps_cpus`),
   OpenWrt `network.globals.packet_steering`. Do not assume another router's setup.
3. If RPS spreads the LAN traffic over N CPUs (no RFS) and XPS maps CPU k to tx
   queue k, `tools/rss-port-pick.py` predicts the instance of a TCP flow (its
   assumptions are listed in its header).
4. Before any experiment, confirm the predictions: short single flows with fixed
   source ports (`iperf3 --cport`), and check that the per-instance `Sent` byte
   deltas of `tc -s qdisc show dev <wan-if>` land on the predicted instance.
5. Use the ports only if every prediction is confirmed. Re-read the RSS key after
   any reboot or interface change: it is usually regenerated.

Notes: `iperf3 -P N --cport P` uses the ports P to P+N-1; concurrent tests must not
share local ports; wait about 3 s between two tests on the same server port.
Result on the tested R86S (8 queues): 32/32 predicted placements confirmed on all
8 instances, for one RSS key.
