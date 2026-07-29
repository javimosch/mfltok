#!/usr/bin/env python3
"""Exhaustive whitespace-boundary corpus.

The cl100k pattern orders `\\s++$` BEFORE `\\s*[\\r\\n]`, and ends with a bare
`\\s` (single char), not `\\s+`. Those three facts interact only on whitespace
runs at/near end-of-string, which random fuzz hits rarely. Enumerate them.
"""
import base64, itertools, sys
import tiktoken

enc_name = sys.argv[1] if len(sys.argv) > 1 else "cl100k_base"
out_path = sys.argv[2] if len(sys.argv) > 2 else "tests/ws.fixture"
enc = tiktoken.get_encoding(enc_name)

ws = [" ", "\n", "\t", "\r", " ", "　"]
anchors = ["", "a", "1", ".", "ab", "!"]

cases = set()
# every whitespace string up to length 4, bare and surrounded by anchors
for n in range(1, 5):
    for combo in itertools.product(ws, repeat=n):
        w = "".join(combo)
        cases.add(w)
        for pre in anchors:
            for post in anchors:
                cases.add(pre + w + post)

with open(out_path, "w") as f:
    n = 0
    for s in sorted(cases):
        if not s:
            continue
        b = s.encode("utf-8")
        ids = enc.encode(s, disallowed_special=())
        f.write("%s %s\n" % (base64.b64encode(b).decode(), ",".join(map(str, ids))))
        n += 1
print("%s: %d whitespace cases -> %s" % (enc_name, n, out_path), file=sys.stderr)
