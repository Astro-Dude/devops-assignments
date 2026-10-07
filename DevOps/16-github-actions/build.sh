#!/usr/bin/env bash
# Build step of the pipeline: produce a versioned, self-describing release bundle
# (build/) that is uploaded as an artifact and later downloaded by the deploy job.
set -euo pipefail

GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo dev)}"
VERSION="$(python3 -c 'import app; print(app.__version__)')"

echo "================================="
echo " Building s16-calculator ${VERSION} (${GIT_SHA})"
echo "================================="
rm -rf build
mkdir -p build

# 1. byte-compile the sources - fails the build on any syntax error
python3 -m compileall -q app

# 2. release bundle: sources + pinned requirements + metadata
tar --exclude='__pycache__' -czf "build/s16-calculator-${VERSION}.tar.gz" app requirements.txt
cat > build/build-info.txt <<INFO
Application : s16-calculator
Version     : ${VERSION}
Git SHA     : ${GIT_SHA}
Built at    : $(date -u +%Y-%m-%dT%H:%M:%SZ)
Built on    : ${RUNNER_NAME:-$(hostname)} (${RUNNER_OS:-$(uname -s)})
Workflow run: ${GITHUB_RUN_ID:-local}
INFO
( cd build && sha256sum ./*.tar.gz > SHA256SUMS 2>/dev/null || shasum -a 256 ./*.tar.gz > SHA256SUMS )

echo
echo "Build files:"
ls -la build
echo
cat build/build-info.txt
echo "Build completed successfully."
