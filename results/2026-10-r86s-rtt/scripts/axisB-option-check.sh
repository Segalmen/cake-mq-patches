#!/bin/sh
# axisB-option-check.sh R "EGRESS_TARGET" "IFB_TARGET" : validity check of an axis-B series: in every run the option strings
# after 'bandwidth 8500Mbit' on eth3 and on the IFB equal the pre-registered TARGET (trailing space tolerated).
# Expected: eth3=1 ifb=1, queues 1 + cake in S, queues 8 + cake_mq in M, no other QoS nft table (*_nft=absent), knobs 0.
R=$1; E=$2; I=$3
for n in S1 M1 S2 M2 S3 M3; do f=$R/$n-state.txt
  e=$(grep -c -F -e "bandwidth 8500Mbit $E" $f); el=$(grep -E "bandwidth 8500Mbit $E *$" $f | wc -l)
  i=$(grep -E "bandwidth 8500Mbit $I *$" $f | wc -l)
  q=$(grep -o -E "queues=[0-9]+ qdisc cake(_mq)?" $f)
  echo "$n options eth3=$el ifb=$i | $q | $(grep -o '[a-z_]*nft=[a-zA-Z]*' $f) | $(grep -o 'prio_d2=[0-9]' $f)"
done
