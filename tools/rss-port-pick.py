#!/usr/bin/env python3
# rss-port-pick.py - predict which cake_mq instance a TCP/IPv4 flow lands on, and pick source ports.
#
# ASSUMPTIONS (check them on YOUR router, see docs/TESTING.md section 5):
#  - the LAN-side NIC computes a Toeplitz RSS hash over src IP, dst IP, src port, dst port;
#  - RPS (no RFS) spreads that traffic over CPUs 0..N-1 listed in order, choosing
#    CPU = (hash * N) >> 32 (kernel reciprocal_scale);
#  - XPS on the WAN interface maps CPU k to tx queue k, i.e. cake_mq instance k+1.
# If any assumption does not hold, the predictions are wrong. Always confirm them with
# short fixed-port flows and per-instance tc byte counters before using the ports.
import argparse, socket, struct, sys

def toeplitz(data, key):
    kb = int.from_bytes(key, 'big'); kl = len(key) * 8; r = 0
    for i in range(len(data) * 8):
        if (data[i // 8] >> (7 - (i % 8))) & 1:
            r ^= (kb >> (kl - 32 - i)) & 0xffffffff
    return r

p = argparse.ArgumentParser(description="Pick TCP source ports per cake_mq instance (see assumptions in the header).")
p.add_argument("--key", required=True, help="RSS key from 'ethtool -x <lan-if>' (aa:bb:..., 40 bytes); re-read after every reboot")
p.add_argument("--src", required=True, help="client IPv4 address as seen by the router LAN interface")
p.add_argument("--dst", required=True, help="server IPv4 address")
p.add_argument("--dport", required=True, type=int, help="server port")
p.add_argument("--cpus", required=True, type=int, help="number of CPUs in the RPS map (= number of cake_mq instances here)")
p.add_argument("--first", type=int, default=40000, help="first source port to examine (default 40000)")
p.add_argument("--per", type=int, default=2, help="ports to list per instance (default 2)")
a = p.parse_args()

key = bytes.fromhex(a.key.replace(':', ''))
if len(key) != 40: sys.exit("STOP: the RSS key must be 40 bytes")
ms = bytes.fromhex("6d5a56da255b0ec24167253d43a38fb0d0ca2bcbae7b30b477cb2da38030f20c6a42b73bbeac01fa")
v = socket.inet_aton("66.9.149.187") + socket.inet_aton("161.142.100.80") + struct.pack(">HH", 2794, 1766)
if toeplitz(v, ms) != 0x51ccc178: sys.exit("STOP: Toeplitz self-check failed")

SA, DA = socket.inet_aton(a.src), socket.inet_aton(a.dst)
pick = {q: [] for q in range(1, a.cpus + 1)}; c = a.first
while any(len(x) < a.per for x in pick.values()) and c < 65536:
    q = ((toeplitz(SA + DA + struct.pack(">HH", c, a.dport), key) * a.cpus) >> 32) + 1
    if len(pick[q]) < a.per: pick[q].append(c)
    c += 1
for q in range(1, a.cpus + 1):
    print("instance %d (tx queue %d): %s" % (q, q - 1, " ".join(str(x) for x in pick[q]) or "none found"))
