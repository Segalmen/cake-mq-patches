# N5105 router, 4 RX queues: which flows get slow, and how it depends on the QoS

**Short version.** On a 4-core N5105 router (Intel igc NICs, 4 queues each) with my own QoS script
(cake_mq egress + IFB ingress) active, 16 of 64 TCP download flows were about 13 % slower than the others
(about 1.60-1.73 Gbit/s against 1.84-1.99 Gbit/s), in 5 download runs over 2 boots. The slow flows are exactly
the ones whose packet processing landed on **one single CPU**: the data (WAN side) and the ACKs (LAN side) were
both processed by the CPU that handles the WAN queue of the data. With the QoS, that CPU was at 98.6-100 % softirq for
every flow, and cake on the IFB dropped 11 000 to 17 000 packets per 5-s flow, for every flow, slow or not. With the QoS removed (same boot),
that CPU stayed at 30-78 % softirq and the same 16 flows were not slower (2.14-2.17 Gbit/s, inside the range of
the others). One run per condition on the second boot: read the "Unknown" section before drawing conclusions.

## Setup
- Router under test: N5105 (4 CPUs), 4 Intel igc ports with 4 combined queues each. OpenWrt 25.12.4,
  r32933-4ccb782af7 (read on the router by the maintainer, SSH banner and LuCI footer); kernel 6.12.87 (read in
  the raw files).
- Client: a PC on the LAN port eth0 (iperf3 3.20, under WSL). Server: an R86S (i3-N305) running `iperf3 -s`,
  reached through the router WAN port eth1. The router does NAT for the client.
- Traffic: one TCP flow per client port, `iperf3 --cport <port> -t 5 -P 1`, ports 40000 to 40063, one after
  the other with a 1-s pause. Download = `iperf3 -R` (the server sends; the data enters the router on eth1).
- Placement on the router (read in every run): RSS Toeplitz, TCP over IPv4 hashed on addresses and ports, the
  indirection table spread over 4 queues; RPS on eth0 = all 4 CPUs, RPS on eth1 = off; the 4 eth1 queue IRQs pinned
  one per CPU (queue k on CPU k); irqbalance not running; RFS off; XPS of the IFB = 0 (read by the maintainer).
- QoS ("active"): my own QoS script (cake_mq egress + IFB ingress): `cake_mq` on the eth1 root (2350 Mbit,
  diffserv4, dual-srchost nat nowash) and `cake_mq` on the root of the IFB of eth1 (2350 Mbit, diffserv4,
  dual-dsthost nat wash ingress), fed by an ingress qdisc and a `mirred` redirect on eth1. Two versions of the
  script were used (runs Up and D1-D3, then D4-D6, after a reboot); the resulting tc setup, compared without
  handles and reference counts, was the same in D3, D4 and D6.
- QoS "removed" (D5): the three qdiscs (eth1 root, eth1 ingress, IFB root) deleted in memory before the run; the
  kernel then put its default `mq` + `fq_codel` on eth1 and on the IFB. The rest of the setup (RPS, IRQ affinity,
  irqbalance, nft ruleset, files) was checked unchanged; the QoS was put back and checked equal after the run.

## Method (measurement kit)
A read-only script on the client opens **one** SSH session to the router and reads it before and after each
flow: per-queue RX counters (`ethtool -S`), `/proc/net/softnet_stat`, `/proc/interrupts`, conntrack lines, and a
fingerprint of the placement (RSS table, hashed fields, RPS masks, IRQ affinities, irqbalance, `tc qdisc show`).
The run stops at the first difference from the reference fingerprint. Nothing is written on the router (except
the QoS removal and its return in D5). Raw files are kept with SHA256 sums. Three versions of the kit were used:

| Kit | Runs | What it measured, in addition to the above |
|---|---|---|
| kit-1 | Up, D1, D2 | ports in ascending order only |
| kit-2 | D3, D4 | port order: ascending, reverse, or random with a recorded seed |
| kit-4 | D5, D6 | `tc -s qdisc show` before/after each flow; CPU time per CPU (`/proc/stat`) over the traffic window only; a baseline reading of the QoS setup; the sha256 of the kit itself; the QoS removal of D5 |

kit-3 was only tested in a VM, not used on the router.

## Runs
| Run | Boot | QoS | Kit | Direction | Port order (seed) |
|---|---|---|---|---|---|
| Up | 1 | active | kit-1 | upload | ascending |
| D1 | 1 | active | kit-1 | download | ascending |
| D2 | 1 | active | kit-1 | download (28 min after D1) | ascending |
| D3 | 1 | active | kit-2 | download | random (20261006) |
| D4 | 2 | active | kit-2 | download | random (20261006) |
| D5 | 2 | **removed** | kit-4 | download | random (20261006) |
| D6 | 2 | active | kit-4 | download | random (20261006) |

All 7 runs: 64 of 64 flows, no stop. Boot 1 and boot 2 have different boot ids (the router was rebooted between
D3 and D4); the RSS key and the RPS hash seed are drawn at each boot, so flows are compared port by port only
within a boot.

## Data (`data/<run>.csv`, one row per client port)
| Column | Meaning |
|---|---|
| `port`, `position` | client port; its position in the run (1 = first) |
| `rx_queue_eth0`, `rx_queue_eth1` | RX queue with the most packets during the flow (`rx_queue_N_packets` deltas) |
| `processed_share_cpu0..3` | share of the `/proc/net/softnet_stat` "processed" delta per CPU (counts on the RPS target CPU, not on the IRQ CPU) |
| `sent_mbps`, `received_mbps` | iperf3 end totals |
| `nic_rx_drops_eth0`, `nic_rx_drops_eth1` | sum of `rx_queue_N_drops` deltas |
| `softirq_pct_cpu0..3` | softirq time per CPU over the traffic window, % of wall time (USER_HZ 100); **kit-4 runs (D5, D6) only** |
| `cake_ingress_drops` | dropped delta of the IFB root qdisc; **D6 only** (in D5 there was no cake qdisc) |

Empty cells mean "not measured by this run's kit"; nothing was reconstructed. `scripts/extract_csv.py` derives the
CSV files from the raw files only.

## Results
| Run | 16 single-CPU flows (Mbit/s sent) | 48 other flows | Data CPU softirq | cake ingress drops per flow |
|---|---|---|---|---|
| Up | 1962-2137 | 1942-2168 | not measured | not measured |
| D1 | 1603-1720 | 1849-1955 | not measured | not measured |
| D2 | 1632-1715 | 1843-1952 | not measured | not measured |
| D3 | 1600-1727 | 1845-1987 | not measured | not measured |
| D4 | 1644-1699 | 1860-1948 | not measured | not measured |
| D5 (QoS removed) | 2137-2172 | 2010-2276 | 29.9-77.9 % | no cake |
| D6 | 1631-1708 | 1864-1973 | 98.6-100.0 % | 10 983-17 220 |

"Single-CPU flow": at least 95 % of the processed delta on one CPU. "Data CPU": the CPU of the IRQ of the eth1
queue that received the data.

## Verified (in the raw files of this router)
- Within a boot, each port lands on the same RX queues (eth0 and eth1) in every run: 64/64 for Up, D1, D2, D3
  (boot 1) and for D4, D5, D6 (boot 2). Across the reboot, only 4 of 64 ports kept both queues. In every run:
  16 ports per queue on each interface, and eth0 and eth1 give the same queue number for 16 of 64 ports.
- 16 single-CPU flows per boot, 4 per eth1 queue: boot 1 ports 40024-40039 (contiguous); boot 2 ports 40008
  40011 40013 40014 40017 40018 40020 40023 40032 40035 40037 40038 40057 40058 40060 40063 (same in D4, D5, D6).
- With the QoS active, the single-CPU flows are slower in every download run, whatever their position (D3:
  positions 3 to 58 in a random order): the slowness follows the port, not the moment of the run. The upload run
  shows no slowdown.
- D5 vs D6 (same boot, one run each): see the results table; with the QoS removed, all flows are faster and the
  single-CPU flows are not slower than the others.
- NIC drops: upload only, eth0, 100 packets on 2 flows; none in the download runs.
- NAT kept the client port for every flow in all 7 runs (conntrack, all readings of a run together). The conntrack
  listing can miss an entry in one reading.

## Read in the kernel sources (6.12.87), not measured
- The IFB picks its queue from the skb queue mapping (`drivers/net/ifb.c`, `ifb_xmit`); with XPS off, a redirected
  packet keeps the RX queue it came from (`net/core/dev.c`, `skb_tx_hash`). The IFB tasklet runs on the CPU that
  queued the packet (`kernel/softirq.c`, `__tasklet_schedule_common`) and re-injects it with
  `netif_receive_skb`, which counts in softnet "processed" (`net/core/dev.c`). So with the QoS, the ingress work
  of a flow (IFB + cake) runs on its data CPU.
- igc takes its RSS key from the kernel's random key (`netdev_rss_key_fill`), drawn at each boot.

## Unknown
- How the CPU time of the data CPU splits between cake, the IFB, the redirect, NAT and the ACKs: not measured.
- Whether saturation of the data CPU is the cause of the cake drops and of the slower single-CPU flows: consistent
  with the data, **not proven**.
- Why exactly 16 flows per boot, and why they were contiguous on boot 1.
- Variability: one run per condition on boot 2 (D5 and D6 were not repeated).
- A setup with the RPS and IRQ affinity of a fresh install (not measured); the upload direction on boot 2 or
  without the QoS (not measured); the client and the server, beyond what iperf3 reports.

## Raw data (offline)
The raw files stay offline, one directory per run. Each directory holds a `SHA256SUMS` file listing every file;
the sha256 of that `SHA256SUMS` file identifies the directory:

| Run | Files | sha256 of SHA256SUMS |
|---|---|---|
| Up | 261 | e7c86ad416afbaaa926e344ba5f1acf88029167f0d9ad65070da4852d706226c |
| D1 | 261 | e34cdfbd06e24c05468c48b8d6accbd5b1d0031a293b809bdac4d9dd7d22fa4f |
| D2 | 261 | 7a510cd59b3f316eec165899578d1d81599682543c580b4ab4dfef1a179b938d |
| D3 | 261 | 61572b13f50492d049a3c2c965e1400658959907215907a3f8504b9da1000598 |
| D4 | 261 | 311518b2d32d4bc4f036d6ed47c85aea7ee88434f8d25148b6086f921794ca00 |
| D5 | 331 | 3eecb7b3cc650cb99313ecc4407fc0461cff20d7a9a60d43adf495ec6de16722 |
| D6 | 326 | aad78d65a33e890713190de5a8859d299b93f9842a9f432c483bac68bd72e533 |

Kit-4 (D5, D6) recorded its own sha256 in each run: 3f5e1467d3ace2ad3af1876bd50a53980aed3edf82706c91f92fe41d4dfd92d4.
Kit-1 and kit-2 did not record theirs.

## Reproduce the CSV files
    python3 scripts/extract_csv.py --ingress-dev ifb4eth1 --out data \
        --run up=<raw dir> --run d1=<raw dir> ... --run d6=<raw dir>
