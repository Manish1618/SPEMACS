#!/usr/bin/env bash
#
# Brings up the two-organisation network and deploys the SPEMACS chaincode.
#
#   bash fabric/scripts/start-network.sh
#
# Two organisations is not decoration. The endorsement policy below requires a
# signature from BOTH Org1 and Org2 for every anchor, which is the only property
# this whole subsystem buys over the local hash chain: no single organisation can
# write or rewrite custody history alone. A single-org network would be strictly
# worse than what SPEMACS already had, at far greater operational cost.

set -euo pipefail

FABRIC_SAMPLES="${FABRIC_SAMPLES:-$HOME/fabric-samples}"
TEST_NETWORK="${FABRIC_SAMPLES}/test-network"
CHANNEL="${FABRIC_CHANNEL:-spemacs}"
CC_NAME="${FABRIC_CHAINCODE:-spemacs-ledger}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_PATH="${SCRIPT_DIR}/../chaincode/spemacs-ledger"

# Both organisations must endorse. This is the line that makes the ledger worth
# running; weakening it to OR() throws away the guarantee.
ENDORSEMENT="${FABRIC_ENDORSEMENT:-AND('Org1MSP.member','Org2MSP.member')}"

if [ ! -d "${TEST_NETWORK}" ]; then
    echo "Test network not found at ${TEST_NETWORK}." >&2
    echo "Run: bash fabric/scripts/setup.sh" >&2
    exit 1
fi

if [ ! -d "${CC_PATH}/node_modules" ]; then
    echo "==> Installing chaincode dependencies"
    (cd "${CC_PATH}" && npm install --omit=dev --no-audit --no-fund)
fi

cd "${TEST_NETWORK}"

echo "==> Taking down any previous network"
./network.sh down || true

echo
echo "==> Starting two organisations with a CA, and creating channel '${CHANNEL}'"
./network.sh up createChannel -c "${CHANNEL}" -ca

echo
echo "==> Deploying '${CC_NAME}'"
echo "    endorsement policy: ${ENDORSEMENT}"
./network.sh deployCC \
    -c "${CHANNEL}" \
    -ccn "${CC_NAME}" \
    -ccp "${CC_PATH}" \
    -ccl javascript \
    -ccep "${ENDORSEMENT}"

cat <<EOF

Network up.

    channel      ${CHANNEL}
    chaincode    ${CC_NAME}
    endorsement  ${ENDORSEMENT}
    peers        peer0.org1 (7051), peer0.org2 (9051)

Next:
    source ${SCRIPT_DIR}/env.sh
    node ${SCRIPT_DIR}/../gateway/server.js

Then in backend/.env:
    FABRIC_ENABLED=true
    FABRIC_GATEWAY_URL=http://127.0.0.1:7090

Tear down with: bash ${SCRIPT_DIR}/stop-network.sh
EOF
