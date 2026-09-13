#!/usr/bin/env bash
#
# One-time setup: fetch fabric-samples, the Fabric binaries and the Docker
# images. Run inside WSL2, not Git Bash -- the Fabric tooling expects a Linux
# Docker socket.
#
#   bash fabric/scripts/setup.sh
#
# Downloads roughly 1 GB of container images. It is idempotent: re-running it
# skips anything already present.

set -euo pipefail

FABRIC_VERSION="${FABRIC_VERSION:-2.5.10}"
CA_VERSION="${CA_VERSION:-1.5.13}"
FABRIC_SAMPLES="${FABRIC_SAMPLES:-$HOME/fabric-samples}"

echo "==> Checking prerequisites"

missing=0
for tool in docker git curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "    MISSING: $tool"
        missing=1
    else
        echo "    ok: $tool"
    fi
done

if ! docker compose version >/dev/null 2>&1; then
    echo "    MISSING: docker compose (v2)"
    missing=1
else
    echo "    ok: docker compose"
fi

if [ "$missing" -ne 0 ]; then
    cat <<'EOF'

Install what is missing first.

On Windows this must run inside WSL2:
    wsl --install                       (Administrator PowerShell, then reboot)
    Install Docker Desktop, then enable
    Settings > Resources > WSL Integration for your distro.

EOF
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo
    echo "Docker is installed but not responding. Start Docker Desktop and retry."
    exit 1
fi

echo
echo "==> Fetching fabric-samples, binaries and images (Fabric ${FABRIC_VERSION})"

if [ -d "${FABRIC_SAMPLES}/test-network" ]; then
    echo "    already present at ${FABRIC_SAMPLES}, skipping download"
else
    mkdir -p "$(dirname "${FABRIC_SAMPLES}")"
    cd "$(dirname "${FABRIC_SAMPLES}")"
    curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh \
        -o install-fabric.sh
    chmod +x install-fabric.sh
    ./install-fabric.sh --fabric-version "${FABRIC_VERSION}" --ca-version "${CA_VERSION}" docker samples binary
    rm -f install-fabric.sh
fi

echo
echo "==> Installing chaincode dependencies"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../chaincode/spemacs-ledger"
npm install --omit=dev --no-audit --no-fund

echo
echo "==> Installing gateway dependencies"
cd "${SCRIPT_DIR}/../gateway"
npm install --no-audit --no-fund

cat <<EOF

Setup complete.

Next:
    bash fabric/scripts/start-network.sh     brings up two orgs and deploys the chaincode
    source fabric/scripts/env.sh             exports identity paths
    node fabric/gateway/server.js            starts the gateway

Then set FABRIC_ENABLED=true in backend/.env and restart the API.
EOF
