#!/bin/bash
# dis.sh <bin> <exact demangled name regex> : disassemble that function (from its address to next symbol)
b=$1; pat=$2; cd "$(dirname $0)"
sort -u $b.map | sort > $b.sorted
line=$(grep -n -E $'\t'"$pat" $b.sorted | head -1 | cut -d: -f1); [ -z "$line" ] && { echo "not found: $pat"; exit 1; }
start=$(sed -n "${line}p" $b.sorted | cut -f1); end=$(awk -F'\t' -v s=$start '$1>s{print $1; exit}' $b.sorted)
echo "# $(sed -n "${line}p" $b.sorted | cut -f2) $start-$end"
objdump -d --no-show-raw-insn --start-address=0x$start --stop-address=0x$end $b | tail -n +7 | sed -E 's/^ *//' | while IFS= read -r l; do a=$(echo "$l" | grep -oE 'bl\s+0x[0-9a-f]+' | grep -oE '[0-9a-f]+$'); if [ -n "$a" ]; then n=$(grep -m1 "^0*$a"$'\t' $b.sorted | cut -f2 | cut -c1-110); echo "$l    ; $n"; else echo "$l"; fi; done
