#!/usr/bin/env bash
#
# Exports the Fabric identity paths the gateway needs.
#
#   source fabric/scripts/env.sh
#
# Defaults point at Org1's User1 in the fabric-samples test network. Override
# FABRIC_SAMPLES if you cloned it somewhere other than ~/fabric-samples.
#
# Which organisation the gateway signs as matters: it is the identity that
# appears as the submitter of every anchor. Org2 must still endorse, because the
# chaincode is deployed with AND('Org1MSP.member','Org2MSP.member') -- that
# two-organisation requirement is the entire reason for using Fabric here.

FABRIC_SAMPLES="${FABRIC_SAMPLES:-$HOME/fabric-samples}"
TEST_NETWORK="${FABRIC_SAMPLES}/test-network"
ORG_DIR="${TEST_NETWORK}/organizations/peerOrganizations/org1.example.com"
USER_MSP="${ORG_DIR}/users/User1@org1.example.com/msp"

if [ ! -d "${TEST_NETWORK}" ]; then
    echo "Test network not found at ${TEST_NETWORK}" >&2
    echo "Run fabric/scripts/setup.sh first, or set FABRIC_SAMPLES." >&2
    return 1 2>/dev/null || exit 1
fi

# The signcert filename differs between cryptogen and Fabric CA, so glob it
# rather than hardcoding either spelling.
SIGNCERT="$(find "${USER_MSP}/signcerts" -name '*.pem' -type f 2>/dev/null | head -1)"

if [ -z "${SIGNCERT}" ]; then
    echo "No signing certificate under ${USER_MSP}/signcerts" >&2
    echo "Has the network been started? Try fabric/scripts/start-network.sh" >&2
    return 1 2>/dev/null || exit 1
fi

export FABRIC_MSP_ID="Org1MSP"
export FABRIC_PEER_ENDPOINT="localhost:7051"
export FABRIC_PEER_HOST_ALIAS="peer0.org1.example.com"
export FABRIC_TLS_CERT_PATH="${ORG_DIR}/peers/peer0.org1.example.com/tls/ca.crt"
export FABRIC_CERT_PATH="${SIGNCERT}"
export FABRIC_KEY_DIR="${USER_MSP}/keystore"

export FABRIC_CHANNEL="${FABRIC_CHANNEL:-spemacs}"
export FABRIC_CHAINCODE="${FABRIC_CHAINCODE:-spemacs-ledger}"
export FABRIC_CONTRACT="${FABRIC_CONTRACT:-EvidenceLedger}"

export GATEWAY_PORT="${GATEWAY_PORT:-7090}"
export GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"

echo "Fabric environment set:"
echo "  MSP        ${FABRIC_MSP_ID}"
echo "  peer       ${FABRIC_PEER_ENDPOINT} (${FABRIC_PEER_HOST_ALIAS})"
echo "  channel    ${FABRIC_CHANNEL}"
echo "  chaincode  ${FABRIC_CHAINCODE}"
echo "  identity   ${FABRIC_CERT_PATH}"
echo
if [ -z "${GATEWAY_TOKEN}" ]; then
    echo "GATEWAY_TOKEN is unset. Set it on both the gateway and the backend"
    echo "(FABRIC_GATEWAY_TOKEN in backend/.env) before exposing the gateway."
fi
