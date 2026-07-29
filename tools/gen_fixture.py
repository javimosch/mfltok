#!/usr/bin/env python3
"""Build a conformance fixture from tiktoken (the reference implementation).

Line format: "<base64(text)> <id,id,...>". base64 keeps the fixture exactly
byte-for-byte what tiktoken encoded -- newlines, NULs and invalid UTF-8
included -- with no escaping rules to get wrong on either side.
"""
import base64, glob, sys, random
import tiktoken

enc_name = sys.argv[1] if len(sys.argv) > 1 else "cl100k_base"
out_path = sys.argv[2] if len(sys.argv) > 2 else "tests/%s.fixture" % enc_name
enc = tiktoken.get_encoding(enc_name)

cases = []

# --- hand-picked adversarial cases ------------------------------------
cases += [
    "", " ", "  ", "\n", "\n\n", "\t", " \n", "\n ", "   \n   ", "\r\n",
    "a", "A", "hello world", "Hello, World!",
    # contractions -- alternative 1, case-insensitive
    "it's", "IT'S", "It'S", "don't", "DON'T", "we're", "WE'RE", "I've",
    "I'VE", "I'm", "I'M", "we'll", "WE'LL", "he'd", "HE'D", "'s", "'S",
    "'re", "''s", "x's", "s'", "'", "''", "'''",
    # numbers -- \p{N}{1,3} splits every 3 digits
    "1", "12", "123", "1234", "12345", "1234567890",
    "3.14159", "1,000,000", "0x1F", "١٢٣٤", "一二三", "Ⅷ", "½",
    # punctuation runs + trailing newlines (alternative 4)
    "!!!", "...", "?!?!", "->", "=>", "!!!\n", "***\n\n", " ...", "  ...",
    "a...b", "(){}[]", "@#$%^&*",
    # whitespace edge cases (alternatives 5/6/7)
    "a  b", "a \n b", "end.   ", "end.\t\t", "   lead", "a\n\n\nb",
    "  \n  \n  ", "word \n", "word\n ", " \t \t ",
    # unicode letters/marks/scripts
    "café", "naïve", "CAFÉ", "Ünïcödé", "ß", "ẞ",
    "日本語", "日本語テキスト", "中文测试", "한국어", "Русский", "עברית",
    "العربية", "ไทย", "हिन्दी", "Ελληνικά",
    # emoji + ZWJ sequences + skin tones + flags
    "😀", "👍🏽", "👨‍👩‍👧‍👦", "🇫🇷", "🏳️‍🌈", "a😀b", "😀😀😀",
    # combining marks
    "é", "à́̂", "́",
    # mixed
    "def foo(x):\n    return x + 1\n",
    "SELECT * FROM t WHERE a='b';",
    '{"key": "value", "n": 42}',
    "https://example.com/a?b=c&d=e",
    "# Heading\n\n- item one\n- item two\n",
    "snake_case camelCase PascalCase kebab-case SCREAMING_SNAKE",
    "a" * 200, "ab" * 150, " " * 50, "\n" * 20,
    # NUL and invalid UTF-8 are exercised via the raw-bytes cases below
]

# --- real source files from the repos we care about -------------------
paths = []
paths += sorted(glob.glob("/home/jarancibia/ai/token-optimizer-cli/**/*.go", recursive=True))
paths += sorted(glob.glob("/home/jarancibia/ai/mfltok/*.src"))
paths += sorted(glob.glob("/home/jarancibia/ai/mfltok/tools/*.py"))
for p in paths[:40]:
    try:
        t = open(p, encoding="utf-8").read()
    except Exception:
        continue
    cases.append(t)
    # also a few random windows, to hit boundaries mid-token
    rnd = random.Random(len(t))
    for _ in range(3):
        if len(t) > 400:
            i = rnd.randrange(0, len(t) - 300)
            cases.append(t[i:i + rnd.randrange(50, 300)])

# --- random unicode fuzz (seeded -> reproducible) ---------------------
rnd = random.Random(20260729)
alphabet = (
    "abcXYZ 0123\n\t.,!?'\"-_/\\()[]{}"
    "éüñß日本語한국어Русскийعربي😀👍🏽́‍️"
)
for _ in range(400):
    n = rnd.randrange(1, 60)
    cases.append("".join(rnd.choice(alphabet) for _ in range(n)))

seen = set()
written = 0
with open(out_path, "w") as f:
    for t in cases:
        b = t.encode("utf-8")
        if b in seen:
            continue
        seen.add(b)
        if not b:
            continue
        ids = enc.encode(t, disallowed_special=())
        f.write("%s %s\n" % (base64.b64encode(b).decode(), ",".join(map(str, ids))))
        written += 1

print("%s: %d cases -> %s" % (enc_name, written, out_path), file=sys.stderr)
