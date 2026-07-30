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
mfltok count     [--vocab NAME] [FILE]   token count as JSON
mfltok countmany [--vocab NAME]          paths on stdin -> JSON array
mfltok scan      [--vocab NAME] [DIR]    walk a repo -> JSON
mfltok encode    [--vocab NAME] [FILE]   token ids as JSON
mfltok selftest  FIXTURE [--vocab N]     conformance check
```

`scan` walks a tree and reports exact per-file cost, top files, and bloat:

```bash
$ mfltok scan . --vocab o200k_base
{"vocab":"o200k_base","root":".","files":517,"tokens":1669425,...
 "skipped":{"vendor_dirs":19,"binary":32,"over_10mb":0,"symlinks":0,"dotfiles":12},
 "top":[{"path":"...","tokens":25632,"lang":"MFL"},...]}
```

`--human` prints a report instead of JSON.

**Every exclusion is counted.** A scanner that silently drops files reads as
"I measured everything" when it did not.

**It honours `.gitignore`** (nested files included) and `.git/info/exclude`. If
the repo says a file is not source, it is not priced. On this repo that gives
exactly the 19 files `git ls-files` reports. Two honest limits: the pattern
support is a subset (no `**`, no `[a-z]` classes, no escapes — unsupported
patterns are *counted and reported*, never silently ignored), and a global
`core.excludesFile` is not read, since that needs git config. On a 3,000-file
repo mfltok scanned 490 files where a git-based oracle suggested ~469; that ~4 %
is not fully attributed and is stated here rather than rounded away.

`scan` **supersedes [token-optimizer-cli](https://github.com/javimosch/token-optimizer-cli)**,
which is now deprecated: its `scan`/`audit`/`summary` were three printers over
one identical computation, and `check` is `mfltok count`. That repo is kept
un-archived on purpose — its Go scanner is the differential oracle below.

`scan` is what forced `stat`/`is_dir`/`file_size`/`is_symlink` into machin
itself ([machin#541](https://github.com/javimosch/machin/pull/541), v0.123.0):
walking a tree, skipping vendor directories and skipping files over 10 MB were
all inexpressible in MFL before it. `is_symlink` is why the walk terminates — a
symlink to a directory is `is_dir=true`, so without `lstat` a link pointing back
up the tree loops forever.

### Validated against the Go implementation

`scan` was written by porting token-optimizer-cli's Go scanner, so the two can
be diffed. On the machin repo (3,000+ files) they first disagreed wildly —
3,215 files / 7.1M tokens vs 557 files / 44.6M — and **each had a distinct bug**:

- **Go** counted extensionless binaries. `bin/machin` (8.1 MB, no extension,
  under the size cap) tokenized to **5,870,023 junk tokens** from one file. Both
  now use a NUL byte in the file's head as the content test, which needs no
  filename list.
- **MFL** skipped dot*files* but descended into dot*directories*, walking three
  whole repo copies under `.claude/worktrees/`.

After both fixes: **517 files / 1,669,425 tokens** (MFL) vs **529 /
1,670,134** (Go). The remaining gap is 12 files and 709 tokens, fully
accounted for and purely a difference in rule: Go excludes dot-paths only at
the repo root (`HasPrefix(rel, ".")`), so `.gitignore` is skipped but
`selfhost/.gitignore` is not; mfltok excludes them at any depth. Neither is
"wrong", but only one is consistent.

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
| **mfltok** (static binary) | **0.08 s** | **57 ms** | **56 MB** |
| Python + `tiktoken` (Rust core) | 0.37 s | 87 ms | 68 MB |

Pure MFL now wins on all three axes against tiktoken's Rust core. Getting there
took two rewrites, and the second only happened because the first measurement
was wrong.

**The rank table is not a hash map.** Keying a `map[string]int` by each token's
hex cost ~470 bytes per entry — 47 MB for cl100k, 85 MB for o200k, before
encoding a single byte. It is now a flat open-addressing table: decoded tokens
live in one `alloc()`'d blob, three int arrays hold (offset, length, rank), and
lookup hashes the bytes in place and compares against the blob with `peek_i8`.
Nothing is allocated per probe. NUL-safety comes free — a length-delimited blob
has no terminator to trip over, so the hex encoding that existed purely to dodge
embedded NULs disappeared with it.

**Loading allocates nothing either.** The bigger surprise: most of the resident
memory was not the table, it was *load*. Each line did `bytes_sub` ×2 +
`bytes_str` ×2 + `base64_decode_bytes` — five arena allocations × 200,000 lines,
none reclaimable until the process exits. Decoding base64 straight out of the
mapped file into the blob removed all of it: **85 MB → 27 MB** to load o200k,
and load time fell from 71 ms to 20 ms.

**What did not work**, recorded so it is not retried: building the lookup key
byte-by-byte in MFL to avoid `bytes_sub`. A `[]string` + `append` + `join` is N
allocations per probe against the two it replaced — measured *worse* on both
axes (202 MB, 190 ms).

An earlier version of this file blamed the then-155 MB peak on the rank map
without measuring it. That was wrong twice over: the map was 47 MB of it, and
the real culprit was transient garbage. Measuring instead of asserting is the
whole point of this repo, so the wrong claim is recorded rather than quietly
replaced.

## Licence

MIT.

