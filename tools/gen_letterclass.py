#!/usr/bin/env python3
"""Targeted corpus for the o200k letter-class backtracking.

o200k alternative 1 is  U* L+  where U={Lu,Lt,Lm,Lo,M} and L={Ll,Lm,Lo,M}.
The classes OVERLAP on {Lm,Lo,M}, so the greedy U* must give characters back
until L+ can match. Bugs live exactly in that hand-off, and random fuzz picks
those categories too rarely. Enumerate short strings over one representative
codepoint per category, plus contractions and the optional prefix char.
"""
import base64, itertools, sys
import tiktoken

enc_name = sys.argv[1] if len(sys.argv) > 1 else "o200k_base"
out_path = sys.argv[2] if len(sys.argv) > 2 else "tests/letterclass.fixture"
enc = tiktoken.get_encoding(enc_name)

reps = {
    "Lu": "A",        # upper
    "Ll": "a",        # lower
    "Lt": "ǅ",   # Dž  titlecase
    "Lm": "ʰ",   # ʰ   modifier letter (in BOTH classes)
    "Lo": "一",   # 一  other letter   (in BOTH classes)
    "Mn": "́",   # ́   combining acute (in BOTH classes)
    "Mc": "ः",   # ः   spacing mark   (in BOTH classes)
    "N":  "1",
    "P":  ".",
    "S":  " ",
}
alpha = list(reps.values())

cases = set()
# every string of length 1..4 over the representatives
for n in range(1, 5):
    for combo in itertools.product(alpha, repeat=n):
        cases.add("".join(combo))

# contractions glued onto every length-2 letter combo
contr = ["'s", "'S", "'t", "'re", "'ve", "'m", "'ll", "'d", "'", "'x"]
for n in range(1, 3):
    for combo in itertools.product(alpha, repeat=n):
        base = "".join(combo)
        for c in contr:
            cases.add(base + c)
            cases.add(base + c + "z")

with open(out_path, "w") as f:
    n = 0
    for s in sorted(cases):
        b = s.encode("utf-8")
        ids = enc.encode(s, disallowed_special=())
        f.write("%s %s\n" % (base64.b64encode(b).decode(), ",".join(map(str, ids))))
        n += 1
print("%s: %d letter-class cases -> %s" % (enc_name, n, out_path), file=sys.stderr)
