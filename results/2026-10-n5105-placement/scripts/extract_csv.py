#!/usr/bin/env python3
"""Derive one CSV per run from the raw files of the traffic kit (cml-traffic.py).

    python3 extract_csv.py --run up=<raw dir> --run d1=<raw dir> ... --ingress-dev ifb4eth1 --out data/

Reads only the raw files of each run directory: NNN-p<port>-before.txt and
-after.txt (ethtool -S, /proc/net/softnet_stat, tc -s qdisc show),
NNN-p<port>-iperf3.json, NNN-p<port>-window.txt (/proc/stat just before and
just after iperf3; kit-4 runs only) and the port order of meta.json. Writes
no address of any kind. Columns that a run did not measure are left empty.

Python 3 standard library only.
"""

import argparse
import csv
import json
import os
import re

CPUS = 4
USER_HZ = 100
QUEUE_RE = re.compile(r'^\s*rx_queue_(\d+)_(packets|drops):\s*(\d+)\s*$')
QDISC_RE = re.compile(r'^qdisc (\S+) (\S+) dev (\S+) (root|parent (\S+))')
SENT_RE = re.compile(r'^\s*Sent (\d+) bytes (\d+) pkt \(dropped (\d+),')


def sections(path):
    out, cur = {}, None
    with open(path) as f:
        for line in f.read().splitlines():
            if line.startswith('@@ '):
                cur = line[3:].strip()
                out[cur] = []
            elif cur is not None:
                out[cur].append(line)
    return out


def queues(lines):
    q = {}
    for l in lines:
        m = QUEUE_RE.match(l)
        if m:
            q.setdefault(int(m.group(1)), {})[m.group(2)] = int(m.group(3))
    return q


def softnet(lines):
    out = {}
    for i, l in enumerate(lines):
        f = l.split()
        if len(f) >= 10:
            out[int(f[12], 16) if len(f) >= 13 else i] = int(f[0], 16)
    return out


def root_drops(lines, dev):
    """Dropped counter of the root qdisc of dev in tc -s qdisc show, or None."""
    key = None
    for l in lines:
        m = QDISC_RE.match(l)
        if m:
            key = (m.group(3), m.group(4))
            continue
        m = SENT_RE.match(l)
        if m and key == (dev, 'root'):
            return int(m.group(3))
    return None


def window(path):
    """softirq share (%) per CPU over the traffic window, or None."""
    halves = open(path).read().split('@@ window end')
    if len(halves) != 2:
        return None
    vals = []
    for h in halves:
        up, cpus = None, {}
        for l in h.splitlines():
            f = l.split()
            if f and re.fullmatch(r'cpu\d+', f[0]):
                v = [int(x) for x in f[1:]]
                cpus[int(f[0][3:])] = v[6]
            elif len(f) == 2 and re.fullmatch(r'[0-9.]+', f[0]):
                up = float(f[0])
        vals.append((up, cpus))
    (u1, c1), (u2, c2) = vals
    if u1 is None or u2 is None or u2 <= u1:
        return None
    return {c: 100.0 * (c2[c] - c1[c]) / USER_HZ / (u2 - u1) for c in c1 if c in c2}


def dominant(qb, qa):
    d = {n: qa[n].get('packets', 0) - qb[n].get('packets', 0) for n in qb if n in qa and 'packets' in qb[n]}
    return max(d, key=d.get) if d and sum(d.values()) > 0 else ''


def drops(qb, qa):
    return sum(qa[n].get('drops', 0) - qb[n].get('drops', 0) for n in qb if n in qa and 'drops' in qb[n])


def run_rows(d, ingress_dev):
    meta = json.load(open(os.path.join(d, 'meta.json')))
    position = {p: i + 1 for i, p in enumerate(meta['ports'])}
    rows = []
    for name in sorted(os.listdir(d)):
        m = re.match(r'^(\d{3})-p(\d+)-before\.txt$', name)
        if not m:
            continue
        tag, port = '%s-p%s' % (m.group(1), m.group(2)), int(m.group(2))
        b = sections(os.path.join(d, tag + '-before.txt'))
        a = sections(os.path.join(d, tag + '-after.txt'))
        ip = json.load(open(os.path.join(d, tag + '-iperf3.json')))['end']
        q0b, q0a = queues(b.get('stats eth0', [])), queues(a.get('stats eth0', []))
        q1b, q1a = queues(b.get('stats eth1', [])), queues(a.get('stats eth1', []))
        sb, sa = softnet(b.get('softnet', [])), softnet(a.get('softnet', []))
        sn = {c: sa[c] - sb[c] for c in sb if c in sa}
        tot = sum(sn.values())
        row = {'port': port, 'position': position[port], 'rx_queue_eth0': dominant(q0b, q0a),
               'rx_queue_eth1': dominant(q1b, q1a)}
        for c in range(CPUS):
            row['processed_share_cpu%d' % c] = '%.4f' % (sn.get(c, 0) / tot) if tot else ''
        row['sent_mbps'] = '%.1f' % (ip['sum_sent']['bits_per_second'] / 1e6)
        row['received_mbps'] = '%.1f' % (ip['sum_received']['bits_per_second'] / 1e6)
        row['nic_rx_drops_eth0'] = drops(q0b, q0a)
        row['nic_rx_drops_eth1'] = drops(q1b, q1a)
        wpath = os.path.join(d, tag + '-window.txt')
        w = window(wpath) if os.path.exists(wpath) else None
        for c in range(CPUS):
            row['softirq_pct_cpu%d' % c] = '%.1f' % w[c] if w and c in w else ''
        db, da = root_drops(b.get('tc-s', []), ingress_dev), root_drops(a.get('tc-s', []), ingress_dev)
        row['cake_ingress_drops'] = (da - db) if db is not None and da is not None and 'tc-s' in b and \
            any(l.startswith('qdisc cake') and ' dev %s ' % ingress_dev in l for l in b['tc-s']) else ''
        rows.append(row)
    return sorted(rows, key=lambda r: r['port'])


def main():
    ap = argparse.ArgumentParser(description='One CSV per run, from the raw files of cml-traffic.py.')
    ap.add_argument('--run', action='append', required=True, help='name=raw directory (repeatable)')
    ap.add_argument('--ingress-dev', required=True, help='IFB device whose root qdisc drops are the cake ingress drops')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cols = (['port', 'position', 'rx_queue_eth0', 'rx_queue_eth1'] +
            ['processed_share_cpu%d' % c for c in range(CPUS)] +
            ['sent_mbps', 'received_mbps', 'nic_rx_drops_eth0', 'nic_rx_drops_eth1'] +
            ['softirq_pct_cpu%d' % c for c in range(CPUS)] + ['cake_ingress_drops'])
    for spec in a.run:
        name, d = spec.split('=', 1)
        rows = run_rows(d, a.ingress_dev)
        with open(os.path.join(a.out, name + '.csv'), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print('%s: %d rows' % (name, len(rows)))


if __name__ == '__main__':
    main()
