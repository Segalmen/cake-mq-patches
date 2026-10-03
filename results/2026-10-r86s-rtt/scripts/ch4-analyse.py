# ch4-analyse.py : series B1-B8 (plain cake S vs cake_mq M, upload), rules of the pre-registration (README).
# Load 1: mean of 1-s intervals with start >= 10 and end <= 25 s. Load 2: sum over the three tests of the mean of their
# 1-s intervals with start >= 10 and end <= 35 s. LOSS iff M <= 0.90 S in 3/3 pairs; GAIN iff M >= 1.10 S in 3/3.
# Descriptive: per-core router CPU busy % (max over 1-s samples), ping p99 in the load-2 window.
import json, re, sys, statistics as st, math
R = sys.argv[1]
def win(path, a, b):
    j = json.load(open(path)); v = [x["sum"]["bits_per_second"] for x in j["intervals"] if x["sum"]["start"] >= a and x["sum"]["end"] <= b]
    return st.mean(v) / 1e9, len(v)
def cpu(path):
    S, cur = [], None
    for l in open(path):
        if l.startswith("=== T"): cur = {}; S.append(cur); continue
        w = l.split()
        if cur is not None and w and w[0].startswith("cpu") and w[0] != "cpu":
            v = list(map(int, w[1:])); cur[w[0]] = (sum(v), v[3] + v[4])
    mx = {}
    for a, b in zip(S, S[1:]):
        for c in b:
            if c in a:
                dt = b[c][0] - a[c][0]; di = b[c][1] - a[c][1]
                if dt > 0: mx[c] = max(mx.get(c, 0), 100.0 * (dt - di) / dt)
    return mx
def p99(run):
    t0 = float(open("%s/%s-t2w.txt" % (R, run)).read()); v = []
    for l in open("%s/%s-ping.txt" % (R, run)):
        m = re.search(r"^\[([\d.]+)\].*time=([\d.]+) ms", l)
        if m and 10 <= float(m.group(1)) - t0 <= 35: v.append(float(m.group(2)))
    v.sort(); return (v[math.ceil(0.99 * len(v)) - 1], len(v)) if v else (float("nan"), 0)
res = {}
for n in ["S1", "M1", "S2", "M2", "S3", "M3"]:
    l1, k1 = win("%s/%s-L1.json" % (R, n), 10, 25)
    parts = [win("%s/%s-L2%s.json" % (R, n, x), 10, 35) for x in "abc"]
    l2 = sum(p[0] for p in parts); mx = cpu("%s/%s-cpu.txt" % (R, n)); pp = p99(n)
    res[n] = (l1, l2)
    print("%s  L1=%.3f Gbit/s (%d int)  L2=%.3f Gbit/s (%s int)  ping p99=%.2f ms (n=%d)  CPU max %%: %s" % (n, l1, k1, l2, "/".join(str(p[1]) for p in parts), pp[0], pp[1], " ".join("%s=%.0f" % (c[3:], mx[c]) for c in sorted(mx))))
for i, name in ((0, "LOAD 1 (1 flow)"), (1, "LOAD 2 (12 flows)")):
    r = [res["M%d" % k][i] / res["S%d" % k][i] for k in (1, 2, 3)]
    v = "LOSS" if all(x <= 0.90 for x in r) else ("GAIN" if all(x >= 1.10 for x in r) else "NO CLEAR DIFFERENCE")
    print("%s : M/S = %s  median %.3f  -> %s" % (name, " / ".join("%.3f" % x for x in r), st.median(r), v))
