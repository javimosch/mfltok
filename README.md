# mfltok

**An exact BPE tokenizer in pure [machin](https://github.com/javimosch/machin) (MFL) — one static binary, no Python, no Rust, no `tiktoken`.**

Counts GPT tokens the way the model actually counts them: real byte-pair encoding over the real rank tables, byte-for-byte identical to [tiktoken](https://github.com/openai/tiktoken) across ~166,000 conformance cases.

```bash
$ echo "hello world" | mfltok count
{"vocab":"cl100k_base","bytes":12,"tokens":3,"load_ms":63,"encode_ms":0}

$ mfltok count main.go --vocab o200k_base
{"vocab":"o200k_base","bytes":1088,"tokens":289,"load_ms":141,"encode_ms":1}
```

## Why this exists

Almost every "token counter" in the wild is `len(text) / 4`. That heuristic is not
close enough to make decisions with. Measured on real Go source against the true
`o200k_base` encoding:

| file | `chars/4` | real | error |
|---|---:|---:|---:|
| `cmd/flags.go` | 248 | 332 | **−25.3 %** |
| `tokenizer/tokenizer.go` | 295 | 391 | **−24.6 %** |
| `scanner/scanner.go` | 1698 | 2074 | **−18.1 %** |
| `main.go` | 272 | 289 | −5.9 % |
| **total** | **4328** | **5320** | **−18.6 %** |

The heuristic under-counts by ~19 %, and — worse — **non-uniformly**. The error is
largest on dense, punctuation-heavy files, which are exactly the files a
context-budgeting tool ranks highest. So the *ranking* is wrong, not just the
total. Any "tokens saved" number built on `chars/4` is measuring its own
rounding error.

This was written to remove that excuse from [token-optimizer-cli](https://github.com/javimosch/token-optimizer-cli),
after [JetBrains showed](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/)
what self-reported token accounting is worth: a tool advertising "96.2 M tokens
saved" while paired A/B billing went **up** 7.6 %.

## Install / build

Needs [machin](https://github.com/javimosch/machin) and a C compiler.

```bash
./build.sh                 # -> ./mfltok            (~111 kB, dynamic)
./build.sh --static        # -> ./mfltok            (~1.2 MB, FROM scratch)
```

Vocabularies are plain `.tiktoken` files (base64 token + rank, one per line):

```bash
mkdir -p vocab
curl -sSLo vocab/cl100k_base.tiktoken https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
curl -sSLo vocab/o200k_base.tiktoken  https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken
```

Point `MFLTOK_VOCAB_DIR` elsewhere if you like (default `./vocab`).

## Use

```
mfltok count  [--vocab NAME] [FILE]   token count as JSON
mfltok encode [--vocab NAME] [FILE]   token ids as JSON
mfltok selftest FIXTURE [--vocab N]   conformance check
```

`FILE` defaults to stdin. `--vocab` is `cl100k_base` (GPT-4, GPT-3.5) or
`o200k_base` (GPT-4o, o-series). Agent-first contract: **stdout is JSON**,
errors go to stderr, exit codes are semantic (`0` ok, `2` usage, `3` missing
vocab, `4` conformance failure).

## Correctness

`./test.sh` checks every case against ids produced by the reference
implementation. Fixtures store the input as base64, so they are exactly the
bytes tiktoken saw — newlines, NULs and invalid UTF-8 included.

| suite | cases | what it covers |
|---|---:|---|
| `cl100k_base` / `o200k_base` | ~576 + ~576 | hand-picked edges, contractions, 15 scripts, emoji/ZWJ/skin-tone, real source files (count varies slightly: it globs this repo's own sources) |
| `fuzz_*` | 20 000 × 2 | seeded random over a boundary-weighted alphabet |
| `ws_*` | 55 944 × 2 | **exhaustive** whitespace strings ≤ 4 chars, bare and anchored |
| `letterclass_o200k` | 13 310 | exhaustive over one codepoint per Unicode category — targets the `U*`/`L+` backtracking |
| **total** | **~166 350** | **all byte-exact** |

Two things the tests caught that reading the spec did not:

- **The published cl100k pattern is not the textbook one.** It uses *possessive*
  quantifiers, has an extra `\s++$` alternative ordered before `\s*[\r\n]`, and
  ends in a bare `\s` — not `\s+`. Hand-tracing predicted a divergence on
  `" \n "`; the exhaustive whitespace suite proved there is none. Enumeration
  beat reasoning.
- **Both vocabularies contain tokens with an embedded NUL** (1 in cl100k, 2 in
  o200k). MFL strings are NUL-terminated, so the obvious `map[string]int` keyed
  by raw token bytes silently truncates. Ranks are keyed by **hex** instead.

## How it works

Three problems, none of which have a library in MFL:

1. **Pretokenization.** The reference patterns are defined with `\p{L}`, `\p{N}`,
   `\p{Lu}`… and a negative lookahead. POSIX ERE — all machin's `regex_*`
   builtins offer — has none of that. So the alternation is implemented
   directly, in order, first-match-wins, with `tools/gen_unicode.py` baking the
   category ranges into sorted flat arrays (`uni_letter`, `uni_number`,
   `uni_space`, and the pre-unioned `uni_upperish`/`uni_lowerish` the o200k
   pattern actually uses) that are binary-searched at runtime — 42 kB of
   generated MFL, regenerable and deterministic.
   o200k's quantifiers are *not* possessive and its two letter classes overlap
   on `{Lm, Lo, M}`, so `U* L+` genuinely backtracks; `try_letter_alt` walks the
   backtrack points in engine order.
2. **The merge loop.** tiktoken's `_byte_pair_merge`: after a merge only two
   neighbouring pair-ranks can change, so they are patched rather than rescanned.
3. **Rank lookup.** Hex-keyed map, with direct-index caches for the 1- and
   2-byte probes that dominate the loop.

## Performance

445 kB of real source, this machine, both producing the identical 214,650 tokens:

| | wall clock (process start → answer) | encode only | peak RSS |
|---|---:|---:|---:|
| **mfltok** (static binary) | **0.15 s** | **72 ms** | 105 MB |
| Python + `tiktoken` (Rust core) | 0.26 s | 87 ms | 68 MB |

Pure MFL edges out tiktoken's Rust core on encode (~1.2×) and wins end-to-end
by ~1.7× because there is no interpreter to boot. Two changes got it there, and
the second only because the first measurement was wrong:

- **Range probes instead of sub-slices.** The merge loop probes ranges of one
  pretoken thousands of times per file. Routing 1- and 2-byte probes straight
  off `byte_at` into a direct-index table removes a `bytes_sub` **and** a
  `to_hex` allocation from the hottest path. In-place compaction of the
  boundary arrays removes another O(merges) of garbage.
- **What did *not* work:** building the hex key byte-by-byte in MFL to avoid
  `bytes_sub` entirely. A `[]string` + `append` + `join` is N allocations per
  probe against the two it replaced — measured *worse* on both axes (202 MB,
  190 ms). The C builtins win for pieces ≥ 3 bytes. It is in the source as a
  comment so nobody re-tries it.

**On memory, and a correction.** An earlier version of this file blamed the
then-155 MB peak on the hex-keyed rank map. That was wrong, and measuring
instead of asserting is the whole point of this repo, so: loading the ranks
alone costs **47 MB** (cl100k) / **85 MB** (o200k). The rest was transient
encode garbage, which is what the changes above removed. It is still above
tiktoken's 68 MB, and the rank map — one interned hex string per token — is the
honest next target.

## Licence

MIT.

