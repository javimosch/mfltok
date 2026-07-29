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
| **mfltok** (static binary) | **0.21 s** | 134 ms | 155 MB |
| Python + `tiktoken` (Rust core) | 0.32 s | 101 ms | 68 MB |

Honest reading: tiktoken's Rust core **out-encodes this by ~1.3×**. mfltok wins
end-to-end only because it has no interpreter to boot — which is the metric that
matters when a CI job or an agent shells out per file, and not otherwise. The
155 MB RSS is the hex-keyed rank map; that is the obvious thing to fix next
(intern keys, or index by a packed integer). It is not competitive on memory.

## Licence

MIT.
