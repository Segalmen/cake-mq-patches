#!/bin/bash
# Measurement functions used for this study (extracted from the lab bench script). Source this file, set R (output dir), then call run13/run14/run15.
# Assumes: router at 192.168.2.1 (ssh root), sqm-scripts section sqm.eth3 (layer_cake), iperf3 server below. Adapt before use.
R=${R:-$PWD/out}; mkdir -p "$R"
SRV=82.197.188.129

run13() {
    n=$1; a=$2
    if [ "$a" = S ]; then m=0; elif [ "$a" = M ]; then m=1; else echo "ARM must be S or M"; return 1; fi
    ssh root@192.168.2.1 "uci set sqm.eth3.use_mq='$m' && uci commit sqm && /etc/init.d/sqm restart && sleep 5" || { echo "ERROR: failed to apply SQM arm $a for $n"; return 1; }
    ssh root@192.168.2.1 "echo \"use_mq=\$(uci get sqm.eth3.use_mq) sqm_enabled=\$(uci get sqm.eth3.enabled)\"; tc qdisc show dev eth3 | head -1; for i in \$(ip -o link show type ifb | awk -F': ' '{print \$2}' | cut -d@ -f1); do echo \"ifb=\$i queues=\$(ls -d /sys/class/net/\$i/queues/tx-* | wc -l) \$(tc qdisc show dev \$i | head -1)\"; done; echo \"rps_eth3=\$(cat /sys/class/net/eth3/queues/rx-*/rps_cpus | tr '\n' ' ')\"; echo \"xps_eth3=\$(cat /sys/class/net/eth3/queues/tx-*/xps_cpus 2>/dev/null | tr '\n' ' ')\"; pgrep -x irqbalance >/dev/null && echo irqbalance=running || echo irqbalance=stopped; for i in \$(awk '/eth3-TxRx/ {sub(\":\",\"\",\$1); print \$1}' /proc/interrupts); do printf 'irq%s=%s ' \$i \$(cat /proc/irq/\$i/smp_affinity_list); done; echo; [ -z \"\$(nft list tables | grep -v 'inet fw4')\" ] && echo extra_qos_nft=absent || echo extra_qos_nft=PRESENT; d=/sys/kernel/debug/cake_mq; for k in tin_share active_hold tin_cap prio_split prio_thresh prio_d2; do printf '%s=%s ' \$k \$(cat \$d/\$k 2>/dev/null); done; echo" | tee $R/$n-state.txt
    ssh root@192.168.2.1 'end=$(( $(cut -d. -f1 /proc/uptime) + 95 )); while [ $(cut -d. -f1 /proc/uptime) -lt $end ]; do echo "=== T $(cut -d" " -f1 /proc/uptime)"; grep "^cpu" /proc/stat; sleep 1; done' > $R/$n-cpu.txt & cpid=$!
    sleep 3
    timeout 45 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 30 --connect-timeout 3000 > $R/$n-L1.json 2>&1 & p1=$!
    wait $p1; r1=$?
    sleep 5
    date +%s.%N > $R/$n-t2w.txt
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2a.json 2>&1 & pa=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5203 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2b.json 2>&1 & pb=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5204 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2c.json 2>&1 & pc=$!
    ping -i 0.2 -w 45 -D 82.197.188.129 > $R/$n-ping.txt 2>&1 & pp=$!
    wait $pa; ra=$?; wait $pb; rb=$?; wait $pc; rc=$?; wait $pp; wait $cpid
    echo "== $n arm=$a rcL1=$r1 rcL2=$ra/$rb/$rc"
}

run14() {
    n=$1; a=$2
    if [ "$a" = A ]; then r=10ms; elif [ "$a" = B ]; then r=100ms; else echo "ARM must be A or B"; return 1; fi
    o="diffserv4 dual-srchost nowash no-split-gso rtt $r raw memlimit 128mb"
    ssh root@192.168.2.1 "uci set sqm.eth3.use_mq='1' && uci set sqm.eth3.eqdisc_opts='$o' && uci commit sqm && /etc/init.d/sqm restart && sleep 5" || { echo "ERROR: failed to apply arm $a for $n"; return 1; }
    ssh root@192.168.2.1 "echo \"use_mq=\$(uci get sqm.eth3.use_mq) eqdisc_opts=\$(uci get sqm.eth3.eqdisc_opts)\"; tc qdisc show dev eth3 | head -1; for i in \$(ip -o link show type ifb | awk -F': ' '{print \$2}' | cut -d@ -f1); do echo \"ifb=\$i queues=\$(ls -d /sys/class/net/\$i/queues/tx-* | wc -l) \$(tc qdisc show dev \$i | head -1)\"; done; echo \"rps_eth3=\$(cat /sys/class/net/eth3/queues/rx-*/rps_cpus | tr '\n' ' ')\"; pgrep -x irqbalance >/dev/null && echo irqbalance=running || echo irqbalance=stopped; for i in \$(awk '/eth3-TxRx/ {sub(\":\",\"\",\$1); print \$1}' /proc/interrupts); do printf 'irq%s=%s ' \$i \$(cat /proc/irq/\$i/smp_affinity_list); done; echo; [ -z \"\$(nft list tables | grep -v 'inet fw4')\" ] && echo extra_qos_nft=absent || echo extra_qos_nft=PRESENT; d=/sys/kernel/debug/cake_mq; for k in tin_share active_hold tin_cap prio_split prio_thresh prio_d2; do printf '%s=%s ' \$k \$(cat \$d/\$k 2>/dev/null); done; echo" | tee $R/$n-state.txt
    ssh root@192.168.2.1 'end=$(( $(cut -d. -f1 /proc/uptime) + 95 )); while [ $(cut -d. -f1 /proc/uptime) -lt $end ]; do echo "=== T $(cut -d" " -f1 /proc/uptime)"; grep "^cpu" /proc/stat; sleep 1; done' > $R/$n-cpu.txt & cpid=$!
    sleep 3
    timeout 45 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 30 --connect-timeout 3000 > $R/$n-L1.json 2>&1 & p1=$!
    wait $p1; r1=$?
    sleep 5
    date +%s.%N > $R/$n-t2w.txt
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2a.json 2>&1 & pa=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5203 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2b.json 2>&1 & pb=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5204 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2c.json 2>&1 & pc=$!
    ping -i 0.2 -w 45 -D 82.197.188.129 > $R/$n-ping.txt 2>&1 & pp=$!
    wait $pa; ra=$?; wait $pb; rb=$?; wait $pc; rc=$?; wait $pp; wait $cpid
    echo "== $n arm=$a rcL1=$r1 rcL2=$ra/$rb/$rc"
}

run15() {
    n=$1; r=$2
    case "$r" in 10|30|100) ;; *) echo "RTT must be 10, 30 or 100"; return 1 ;; esac
    o="diffserv4 dual-srchost nowash no-split-gso rtt ${r}ms raw memlimit 128mb"
    ssh root@192.168.2.1 "uci set sqm.eth3.use_mq='1' && uci set sqm.eth3.eqdisc_opts='$o' && uci commit sqm && /etc/init.d/sqm restart && sleep 5" || { echo "ERROR: failed to apply rtt $r for $n"; return 1; }
    ssh root@192.168.2.1 "echo \"use_mq=\$(uci get sqm.eth3.use_mq) eqdisc_opts=\$(uci get sqm.eth3.eqdisc_opts)\"; tc qdisc show dev eth3 | head -1; for i in \$(ip -o link show type ifb | awk -F': ' '{print \$2}' | cut -d@ -f1); do echo \"ifb=\$i queues=\$(ls -d /sys/class/net/\$i/queues/tx-* | wc -l) \$(tc qdisc show dev \$i | head -1)\"; done; echo \"rps_eth3=\$(cat /sys/class/net/eth3/queues/rx-*/rps_cpus | tr '\n' ' ')\"; pgrep -x irqbalance >/dev/null && echo irqbalance=running || echo irqbalance=stopped; for i in \$(awk '/eth3-TxRx/ {sub(\":\",\"\",\$1); print \$1}' /proc/interrupts); do printf 'irq%s=%s ' \$i \$(cat /proc/irq/\$i/smp_affinity_list); done; echo; [ -z \"\$(nft list tables | grep -v 'inet fw4')\" ] && echo extra_qos_nft=absent || echo extra_qos_nft=PRESENT; d=/sys/kernel/debug/cake_mq; for k in tin_share active_hold tin_cap prio_split prio_thresh prio_d2; do printf '%s=%s ' \$k \$(cat \$d/\$k 2>/dev/null); done; echo" | tee $R/$n-state.txt
    ssh root@192.168.2.1 'end=$(( $(cut -d. -f1 /proc/uptime) + 95 )); while [ $(cut -d. -f1 /proc/uptime) -lt $end ]; do echo "=== T $(cut -d" " -f1 /proc/uptime)"; grep "^cpu" /proc/stat; sleep 1; done' > $R/$n-cpu.txt & cpid=$!
    sleep 3
    timeout 45 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 30 --connect-timeout 3000 > $R/$n-L1.json 2>&1 & p1=$!
    wait $p1; r1=$?
    sleep 5
    date +%s.%N > $R/$n-t2w.txt
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5202 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2a.json 2>&1 & pa=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5203 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2b.json 2>&1 & pb=$!
    timeout 60 iperf3 -4 -J -C cubic -c $SRV -p 5204 -t 40 -P 4 --connect-timeout 3000 > $R/$n-L2c.json 2>&1 & pc=$!
    ping -i 0.2 -w 45 -D 82.197.188.129 > $R/$n-ping.txt 2>&1 & pp=$!
    wait $pa; ra=$?; wait $pb; rb=$?; wait $pc; rc=$?; wait $pp; wait $cpid
    echo "== $n rtt=${r}ms rcL1=$r1 rcL2=$ra/$rb/$rc"
}
