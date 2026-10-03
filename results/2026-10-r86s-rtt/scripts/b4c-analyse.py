# b4c-analyse.py : series B4C (pre-registered rule: see README). Validity per run (iperf3 rc via JSON 'error',
# option strings of the arm on eth3 and IFB, cake_mq + 8 IFB queues, no other QoS nft table, knobs 0), then load 2 (primary,
# sum of three tests, 1-s intervals start>=10 end<=35) and load 1 (descriptive). Pair i = (Ai, Bi), ratio A/B.
# CONFIRMED iff A/B <= 0.95 in >= 4 of 5 valid pairs AND median <= 0.95; NOT CONFIRMED iff median >= 0.98; else INCONCLUSIVE;
# fewer than 5 valid pairs: INCONCLUSIVE.
import json, re, sys, statistics as st
R = sys.argv[1]
EG = "diffserv4 dual-srchost nat nowash no-ack-filter no-split-gso rtt %s raw overhead 0 memlimit 128Mb"
IG = "diffserv4 dual-dsthost nat wash ingress no-ack-filter no-split-gso rtt 10ms raw overhead 0 memlimit 128Mb"
def win(p, a, b):
    j = json.load(open(p))
    if "error" in j or not j.get("intervals"): return None
    v = [x["sum"]["bits_per_second"] for x in j["intervals"] if x["sum"]["start"] >= a and x["sum"]["end"] <= b]
    return st.mean(v) / 1e9 if v else None
def valid(n):
    s = open("%s/%s-state.txt" % (R, n)).read(); r = "10ms" if n[0] == "A" else "100ms"
    ok = re.search(r"qdisc cake_mq \S+ root bandwidth 8500Mbit " + re.escape(EG % r) + r" *$", s, re.M) is not None
    ok &= re.search(r"queues=8 qdisc cake_mq \S+ root bandwidth 8500Mbit " + re.escape(IG) + r" *$", s, re.M) is not None
    ok &= "_nft=absent" in s and all("%s=0" % k in s for k in ("tin_share", "active_hold", "tin_cap", "prio_split", "prio_thresh", "prio_d2"))
    return ok
res = {}
for n in ["A1", "B1", "B2", "A2", "A3", "B3", "B4", "A4", "A5", "B5"]:
    l1 = win("%s/%s-L1.json" % (R, n), 10, 25); p = [win("%s/%s-L2%s.json" % (R, n, x), 10, 35) for x in "abc"]
    l2 = sum(p) if None not in p else None; v = valid(n) and l1 is not None and l2 is not None
    res[n] = (v, l1, l2)
    print("%s  %s  L1=%s  L2=%s (%s)" % (n, "VALID  " if v else "INVALID", "%.3f" % l1 if l1 is not None else "-", "%.3f" % l2 if l2 is not None else "-", " / ".join("%.3f" % x if x is not None else "-" for x in p)))
pairs = [k for k in range(1, 6) if res["A%d" % k][0] and res["B%d" % k][0]]
r2 = [res["A%d" % k][2] / res["B%d" % k][2] for k in pairs]; r1 = [res["A%d" % k][1] / res["B%d" % k][1] for k in pairs]
print("valid pairs: %s" % pairs)
print("LOAD 2 (primary) A/B: %s  median %.3f  pairs <= 0.95: %d" % (" / ".join("%.3f" % x for x in r2), st.median(r2) if r2 else float("nan"), sum(x <= 0.95 for x in r2)))
print("LOAD 1 (descriptive) A/B: %s" % " / ".join("%.3f" % x for x in r1))
if len(pairs) < 5: v = "INCONCLUSIVE (fewer than 5 valid pairs)"
elif sum(x <= 0.95 for x in r2) >= 4 and st.median(r2) <= 0.95: v = "CONFIRMED"
elif st.median(r2) >= 0.98: v = "NOT CONFIRMED"
else: v = "INCONCLUSIVE"
print("PRE-REGISTERED VERDICT (see README): %s" % v)
