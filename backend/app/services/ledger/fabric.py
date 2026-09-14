"""Fabric backend -- anchors ledger blocks to chaincode via the Node gateway.

Why a gateway process sits in between: Hyperledger Fabric's v2.4+ Gateway SDKs
are published for Go, Node and Java, not Python. Rather than hand-roll gRPC and
endorsement handling against fabric-protos, the supported Node SDK runs as a
small sidecar (fabric/gateway) and exposes a narrow HTTP face to this module.
The sidecar is the only thing holding Fabric identity material.

This module never raises into a request path. Every call returns a result object
and the caller decides; an unreachable ledger leaves anchors PENDING in the
outbox rather than failing an evidence write.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AnchorResult:
    ok: bool
    tx_id: Optional[str] = None
    error: Optional[str] = None
    # True when the chaincode reported this anchor_id was already committed.
    # An outbox retry that lands twice is a success, not a conflict.
    duplicate: bool = False


@dataclass
class GatewayStatus:
    reachable: bool
    detail: str
    channel: Optional[str] = None
    chaincode: Optional[str] = None
    msp_id: Optional[str] = None


def enabled() -> bool:
    return bool(settings.FABRIC_ENABLED)


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = (settings.FABRIC_GATEWAY_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _url(path: str) -> str:
    return f"{settings.FABRIC_GATEWAY_URL.rstrip('/')}{path}"


def status() -> GatewayStatus:
    """Ask the gateway whether it can reach the network. Never raises."""
    if not enabled():
        return GatewayStatus(
            reachable=False,
            detail="Fabric anchoring is disabled (FABRIC_ENABLED=false). The local "
                   "hash-chained ledger is the sole integrity record.",
        )
    try:
        response = requests.get(
            _url("/health"), headers=_headers(), timeout=settings.FABRIC_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        return GatewayStatus(reachable=False, detail=f"Gateway unreachable: {exc}")

    if response.status_code != 200:
        return GatewayStatus(
            reachable=False,
            detail=f"Gateway returned {response.status_code}: {response.text[:200]}",
        )

    body = response.json()
    return GatewayStatus(
        reachable=bool(body.get("ready")),
        detail=body.get("detail") or "Gateway ready.",
        channel=body.get("channel"),
        chaincode=body.get("chaincode"),
        msp_id=body.get("mspId"),
    )


def submit_anchor(anchor_id: str, action: str, payload: Dict[str, Any]) -> AnchorResult:
    """Submit one anchor to the chaincode. Idempotent on anchor_id."""
    if not enabled():
        return AnchorResult(ok=False, error="Fabric anchoring is disabled.")

    body = {"anchorId": anchor_id, "action": action, "payload": payload}
    try:
        response = requests.post(
            _url("/anchors"),
            headers=_headers(),
            json=body,
            timeout=settings.FABRIC_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return AnchorResult(ok=False, error=f"network error: {exc}")

    if response.status_code in (200, 201):
        data = response.json()
        return AnchorResult(
            ok=True,
            tx_id=data.get("txId"),
            duplicate=bool(data.get("duplicate")),
        )

    # 409 is the gateway telling us the chaincode already holds this anchor_id.
    # That is exactly what a retried outbox row looks like, so treat it as done.
    if response.status_code == 409:
        data = {}
        try:
            data = response.json()
        except ValueError:
            pass
        return AnchorResult(ok=True, tx_id=data.get("txId"), duplicate=True)

    return AnchorResult(
        ok=False, error=f"gateway returned {response.status_code}: {response.text[:300]}"
    )


def get_anchor(evidence_id: str) -> Optional[Dict[str, Any]]:
    """Latest chaincode anchor for one evidence item, or None."""
    if not enabled():
        return None
    try:
        response = requests.get(
            _url(f"/anchors/{evidence_id}"),
            headers=_headers(),
            timeout=settings.FABRIC_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Fabric get_anchor failed for %s: %s", evidence_id, exc)
        return None
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.warning(
            "Fabric get_anchor for %s returned %s", evidence_id, response.status_code
        )
        return None
    return response.json()


def get_anchor_history(evidence_id: str) -> List[Dict[str, Any]]:
    """Every chaincode version of this evidence key, oldest first.

    This is Fabric's own GetHistoryForKey, which is why the chaincode does not
    maintain a hash chain of its own -- the platform already provides one.
    """
    if not enabled():
        return []
    try:
        response = requests.get(
            _url(f"/anchors/{evidence_id}/history"),
            headers=_headers(),
            timeout=settings.FABRIC_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Fabric history failed for %s: %s", evidence_id, exc)
        return []
    if response.status_code != 200:
        return []
    body = response.json()
    return body.get("history", []) if isinstance(body, dict) else []


def verify_anchor(evidence_id: str, sha256: str) -> Dict[str, Any]:
    """Ask the chaincode whether it holds this digest for this evidence item."""
    if not enabled():
        return {"checked": False, "detail": "Fabric anchoring is disabled."}
    try:
        response = requests.post(
            _url("/anchors/verify"),
            headers=_headers(),
            json={"evidenceId": evidence_id, "sha256": sha256},
            timeout=settings.FABRIC_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"checked": False, "detail": f"Gateway unreachable: {exc}"}

    if response.status_code != 200:
        return {
            "checked": False,
            "detail": f"Gateway returned {response.status_code}.",
        }

    body = response.json()
    return {
        "checked": True,
        "match": bool(body.get("match")),
        "anchored_sha256": body.get("anchoredSha256"),
        "tx_id": body.get("txId"),
        "detail": body.get("detail") or "",
    }
