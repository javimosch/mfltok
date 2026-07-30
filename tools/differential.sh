#!/bin/sh
# Differential check: mfltok scan vs the legacy Go scanner in
# token-optimizer-cli, on the same tree.
#
# token-optimizer-cli is DEPRECATED as a product -- mfltok scan supersedes it --
# but its Go scanner is kept as an independent second implementation of the same
# spec, because that is what caught two real bugs that 166k conformance cases
# did not: the Go side counted extensionless binaries (5,870,023 junk tokens
# from one 8.1MB file), the MFL side descended into dot-directories. Neither bug
# is visible from inside its own implementation.
#
# A non-zero token delta here is a finding, not noise. Investigate before
# shipping.
#
# KNOWN, ACCEPTED DIFFERENCES:
#  1. The Go scanner excludes dot-paths only at the repo ROOT; mfltok excludes
#     them at any depth. On the machin repo: 12 files, 709 tokens.
#  2. mfltok treats .tiktoken and .fixture as data, the Go scanner does not. On
#     the mfltok repo itself that is a 12.4M-token gap (the vocab files are
#     5.2MB of base64).
#
# Note on (2): those two extensions are REPO-SPECIFIC hardcoding in mfltok --
# the same sin as the Go scanner naming its own binary in a skipFiles list,
# which is criticised in this repo's own README. The principled fix is for the
# scan to honour .gitignore (both files are gitignored here) rather than to grow
# an extension list per repo. Not done yet; recorded so it is not forgotten.
#
# Run the oracle on a tree WITHOUT generated data artifacts for a clean signal.
set -e
ROOT="${1:-.}"
GO_BIN="${GO_BIN:-$HOME/ai/token-optimizer-cli/token-optimizer-cli}"
MFLTOK="${MFLTOK:-$(dirname "$0")/../mfltok}"

[ -x "$GO_BIN" ] || { echo "oracle missing: $GO_BIN (build token-optimizer-cli)" >&2; exit 3; }

echo "tree: $ROOT"
m=$("$MFLTOK" scan "$ROOT" --vocab o200k_base | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["files"],d["tokens"])')
g=$(TOC_NO_DEPRECATION=1 "$GO_BIN" summary "$ROOT" | awk '/^Files:/{f=$2} /^Total tokens:/{t=$3} END{print f, t}')
echo "  mfltok (MFL): $m"
echo "  legacy (Go) : $g"
[ "$m" = "$g" ] && { echo "  IDENTICAL"; exit 0; }
echo "  DIVERGENT — investigate (see header)"
exit 1
