#!/bin/sh
# Run every conformance fixture. Exits non-zero if any case diverges from
# tiktoken, or if any fixture line failed to parse (skipped != 0).
set -e
cd "$(dirname "$0")"
if [ ! -f tests/ws_o200k.fixture ]; then
    echo "fixtures missing -- run ./setup.sh first" >&2
    exit 3
fi
fail=0
total=0

check() {
    out=$(./mfltok selftest "tests/$1.fixture" --vocab "$2" 2>&1 | head -1)
    n=$(printf '%s' "$out" | sed -n 's/.*"cases":\([0-9]*\).*/\1/p')
    total=$((total + ${n:-0}))
    case "$out" in
        *'"ok":true'*) printf '  ok   %-22s %s\n' "$1" "$out" ;;
        *) printf '  FAIL %-22s %s\n' "$1" "$out"; fail=1 ;;
    esac
}

echo "conformance vs tiktoken:"
check cl100k_base        cl100k_base
check fuzz_cl100k        cl100k_base
check ws_cl100k          cl100k_base
check o200k_base         o200k_base
check fuzz_o200k         o200k_base
check ws_o200k           o200k_base
check letterclass_o200k  o200k_base
echo "total cases: $total"
[ "$fail" = 0 ] || { echo "FAILED"; exit 4; }
echo "all byte-exact."
