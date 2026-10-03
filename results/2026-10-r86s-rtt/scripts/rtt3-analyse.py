# rtt3-analyse.py : series RTT3 (pre-registered rule: see README). Validity per run (iperf3 JSON error, egress and IFB
# strings of the arm, cake_mq + 8 IFB queues, no other QoS nft table, knobs 0); a round with any invalid run is excluded.
# Load 2 primary (sum of three tests, 1-s intervals start>=10 end<=35). Q = T30/T100 per round; verdict per the README rule.
# Descriptive: T10/T100, position P = (T30-T10)/(T100-T10), and the excluded round's values.
import json, re, sys, statistics as st
R = sys.argv[1]
EG = "diffserv4 dual-srchost nat nowash no-ack-filter no-split-gso rtt %sms raw overhead 0 memlimit 128Mb"
IG = "diffserv4 dual-dsthost nat wash ingress no-ack-filter no-split-gso rtt 10ms raw overhead 0 memlimit 128Mb"
def win(p, a, b):
    j = json.load(open(p))
    if "error" in j or not j.get("intervals"): return None, j.get("error")
    v = [x["sum"]["bits_per_second"] for x in j["intervals"] if x["sum"]["start"] >= a and x["sum"]["end"] <= b]
    return (st.mean(v) / 1e9 if v else None), None
def state_ok(n, r):
    s = open("%s/%s-state.txt" % (R, n)).read()
    ok = re.search(r"qdisc cake_mq \S+ root bandwidth 8500Mbit " + re.escape(EG % r) + r" *$", s, re.M) is not None
    ok &= re.search(r"queues=8 qdisc cake_mq \S+ root bandwidth 8500Mbit " + re.escape(IG) + r" *$", s, re.M) is not None
    return ok and "_nft=absent" in s and all("%s=0" % k in s for k in ("tin_share", "active_hold", "tin_cap", "prio_split", "prio_thresh", "prio_d2"))
T, V = {}, {}
for k in range(1, 6):
    for r in ("10", "30", "100"):
        n = "R%d-%s" % (k, r); l1, e1 = win("%s/%s-L1.json" % (R, n), 10, 25)
        parts = [win("%s/%s-L2%s.json" % (R, n, x), 10, 35) for x in "abc"]
        l2 = sum(p[0] for p in parts) if all(p[0] is not None for p in parts) else None
        errs = [p[1] for p in parts if p[1]] + ([e1] if e1 else [])
        V[n] = state_ok(n, r) and l1 is not None and l2 is not None; T[n] = (l1, l2)
        print("%-7s %s  L1=%s  L2=%s%s" % (n, "VALID  " if V[n] else "INVALID", "%.3f" % l1 if l1 else "-", "%.3f" % l2 if l2 else "-", ("  ERROR: " + "; ".join(errs)) if errs else ""))
rounds = [k for k in range(1, 6) if all(V["R%d-%s" % (k, r)] for r in ("10", "30", "100"))]
print("valid rounds: %s" % rounds)
Q = {k: T["R%d-30" % k][1] / T["R%d-100" % k][1] for k in range(1, 6) if T["R%d-30" % k][1] and T["R%d-100" % k][1]}
q = [Q[k] for k in rounds]
print("Q = T30/T100 (valid rounds): %s  median %s" % (" / ".join("%.3f" % x for x in q), "%.3f" % st.median(q) if q else "-"))
if len(rounds) < 5: v = "INCONCLUSIVE (fewer than 5 valid rounds)"
elif sum(x >= 0.98 for x in q) >= 4 and st.median(q) >= 0.98: v = "30ms SUFFICES"
elif sum(x <= 0.95 for x in q) >= 4 and st.median(q) <= 0.95: v = "30ms DOES NOT SUFFICE"
else: v = "INTERMEDIATE"
print("PRE-REGISTERED VERDICT (see README): %s" % v)
print("DESCRIPTIVE per round (all rounds with the needed values):")
for k in range(1, 6):
    t10, t30, t100 = (T["R%d-%s" % (k, r)][1] for r in ("10", "30", "100"))
    p = (t30 - t10) / (t100 - t10) if None not in (t10, t30, t100) and t100 != t10 else None
    print("  round %d%s: T10=%s T30=%s T100=%s  Q=%s  T10/T100=%s  P=%s" % (k, "" if k in rounds else " (EXCLUDED)", *("%.3f" % x if x else "-" for x in (t10, t30, t100)), "%.3f" % Q[k] if k in Q else "-", "%.3f" % (t10 / t100) if t10 and t100 else "-", "%.2f" % p if p is not None else "-"))
