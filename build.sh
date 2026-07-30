#!/bin/sh
# Compose the MFL modules and build. `--static` for a FROM-scratch binary.
set -e
SRC="src_unicode.src src_ignore.src src_bpe.src src_pretok.src src_pretok200k.src src_scan.src src_selftest.src app.src"
machin encode $SRC > mfltok.mfl
machin build "$@" mfltok.mfl -o mfltok
ls -la mfltok
