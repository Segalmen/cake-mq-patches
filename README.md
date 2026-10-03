# cake-mq-patches

Experimental kernel patches for **cake_mq** (multi-queue CAKE), as shipped
in OpenWrt 25.12 (kernel 6.12 backport).

**Status: experimental, not for production.** Validated on one router
model only (Intel N5105, i226, 4 queues). Feedback from other hardware is
very welcome: see [docs/TESTING.md](docs/TESTING.md).

## The problem

cake_mq runs one CAKE instance per hardware queue and splits the global
rate between the active instances. Every instance also recomputes its
DiffServ tin thresholds from its **local** share, so priority traffic
(EF, CS5, CS4...) that lands on one instance only gets a fraction of the
priority it gets with plain cake: about **−75 %** in diffserv4 for a
single priority flow, in both directions.

## The patches

| Patch | Knob (debugfs `cake_mq/`) | What it does |
|---|---|---|
| [720](patches/720-net-sched-sch_cake-mq-per-tin-active-share.patch) | `tin_share` | each tin's global threshold is split among the instances that recently carried that tin |
| [729](patches/729-net-sched-sch_cake-mq-tin-cap.patch) (needs 720) | `tin_cap` | a priority tin never exceeds `tin_cap` % of its instance, so it cannot starve the lower tins sharing that instance |

Both knobs are **off by default** (stock behaviour) and can be changed at
runtime, no reboot:

```
echo 1  > /sys/kernel/debug/cake_mq/tin_share
echo 8  > /sys/kernel/debug/cake_mq/active_hold
echo 90 > /sys/kernel/debug/cake_mq/tin_cap
```

## Results (N5105, 2350 Mbit/s, diffserv4)

| Case | stock cake_mq | 720 | 720 + 729 (`tin_cap=90`) |
|---|---|---|---|
| 1 priority flow vs 16 BE flows (download) | −75 % vs plain cake | ±3 % | −10 % |
| same, upload | −75 % | −2 % to +9 % | not measured |
| ping sharing the instance of an 800 Mbit/s priority flow | < 4 ms | 105–217 ms | 2–4 ms |

720 and 729 are validated in diffserv3, diffserv4 and diffserv8 (download,
same behaviour in the three modes; in diffserv3 the priority flow is EF,
as CS4 falls into Best Effort): see section 4 of the 729 README.

Details, method and limitations: [720 README](docs/720-cake-mq-per-tin-active-share-README.md),
[729 README](docs/729-cake-mq-tin-cap-README.md).

## System setup matters

On the test router, cake_mq only matched plain cake with one NIC queue
pinned per CPU core, RPS off on the WAN and irqbalance stopped. With the
default settings (RPS on, irqbalance running) throughput was lower and
unstable. See section 5 of the 720 README.

## Installation

Copy the patches into `target/linux/generic/hack-6.12/` of an OpenWrt
25.12 buildroot (729 after 720) and build an image. They apply on the
stock 25.12 cake_mq code.

## License

GPL-2.0, like the kernel code they modify.

## Results

- [cake_mq vs plain CAKE on an 8-core router: the `rtt` setting matters](results/2026-10-r86s-rtt/README.md) (R86S, 10 Gbit/s, October 2026)
