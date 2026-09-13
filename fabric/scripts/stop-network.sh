#!/usr/bin/env bash
#
# Tears the network down and removes its volumes.
#
#   bash fabric/scripts/stop-network.sh
#
# This destroys the ledger. Anchors already delivered are gone; the SPEMACS
# local chain and the ledger_anchors outbox are untouched, so the backend keeps
# working and simply reports Fabric as unreachable.
#
# Re-anchoring after a rebuild is not automatic: rows already marked ANCHORED
# are not re-sent. Reset them deliberately if you want a fresh network to carry
# the existing history:
#
#   UPDATE ledger_anchors SET status='PENDING', fabric_tx_id=NULL, attempts=0;

set -euo pipefail

FABRIC_SAMPLES="${FABRIC_SAMPLES:-$HOME/fabric-samples}"
TEST_NETWORK="${FABRIC_SAMPLES}/test-network"

if [ ! -d "${TEST_NETWORK}" ]; then
    echo "Nothing to stop: no test network at ${TEST_NETWORK}."
    exit 0
fi

cd "${TEST_NETWORK}"
./network.sh down

echo
echo "Network down. The SPEMACS API continues on its local ledger."
echo "Set FABRIC_ENABLED=false in backend/.env to stop it queueing anchors."
