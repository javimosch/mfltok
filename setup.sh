#!/bin/sh
# Fetch the vocabularies and regenerate every conformance fixture.
#
# Fixtures are NOT committed (they are tens of MB and derived). Every generator
# is seeded, so this reproduces the exact corpus the README reports -- given the
# same tiktoken and the same Python Unicode version, which are printed below.
set -e
cd "$(dirname "$0")"

mkdir -p vocab tests
for e in cl100k_base o200k_base; do
    if [ ! -f "vocab/$e.tiktoken" ]; then
        echo "fetching $e"
        curl -sSLo "vocab/$e.tiktoken" \
            "https://openaipublic.blob.core.windows.net/encodings/$e.tiktoken"
    fi
done

python3 - <<'EOF'
import sys, unicodedata, tiktoken
print("python        %s" % sys.version.split()[0])
print("unicodedata   %s" % unicodedata.unidata_version)
print("tiktoken      %s" % getattr(tiktoken, "__version__", "unknown"))
EOF

python3 tools/gen_unicode.py src_unicode.src

python3 tools/gen_fixture.py    cl100k_base tests/cl100k_base.fixture
python3 tools/gen_fixture.py    o200k_base  tests/o200k_base.fixture
python3 tools/gen_fuzz.py       cl100k_base tests/fuzz_cl100k.fixture 20000
python3 tools/gen_fuzz.py       o200k_base  tests/fuzz_o200k.fixture  20000
python3 tools/gen_ws.py         cl100k_base tests/ws_cl100k.fixture
python3 tools/gen_ws.py         o200k_base  tests/ws_o200k.fixture
python3 tools/gen_letterclass.py o200k_base tests/letterclass_o200k.fixture

echo "setup done -- now: ./build.sh && ./test.sh"
