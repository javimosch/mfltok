#!/usr/bin/env python3
"""Large seeded fuzz corpus -- reproducible, and deliberately weighted toward
the pretokenizer's boundary cases (whitespace runs, marks, ZWJ, RTL, digits)."""
import base64, random, sys
import tiktoken

enc_name = sys.argv[1] if len(sys.argv) > 1 else "cl100k_base"
out_path = sys.argv[2] if len(sys.argv) > 2 else "tests/fuzz.fixture"
count = int(sys.argv[3]) if len(sys.argv) > 3 else 20000

enc = tiktoken.get_encoding(enc_name)
rnd = random.Random(20260729)

alpha = list("abcdefgXYZ 0123456789.,!?'\"-_/\\()[]{}<>@#$%^&*+=|~`;:")
alpha += list("\n\r\t")
alpha += list("éüñßÿÆœ")
alpha += list("日本語中文한국어РусскийΕλληνικάעבריתالعربية")
alpha += list("हिन्दीไทย")
alpha += ["\U0001F600", "\U0001F44D\U0001F3FD", "\U0001F1EB\U0001F1F7"]
alpha += ["́", "‍", "️"]           # combining, ZWJ, VS16
alpha += [" ", " ", "　", " "]  # exotic spaces
alpha += ["½", "Ⅷ", "٣", "๙"]  # numeric forms
# heavy weighting on the characters that drive alternation choices
alpha += [" "] * 12 + ["\n"] * 6 + ["'"] * 6 + ["\t"] * 3

with open(out_path, "w") as f:
    n = 0
    for _ in range(count):
        s = "".join(rnd.choice(alpha) for _ in range(rnd.randrange(1, 80)))
        b = s.encode("utf-8")
        ids = enc.encode(s, disallowed_special=())
        f.write("%s %s\n" % (base64.b64encode(b).decode(), ",".join(map(str, ids))))
        n += 1
print("%s: %d fuzz cases -> %s" % (enc_name, n, out_path), file=sys.stderr)
