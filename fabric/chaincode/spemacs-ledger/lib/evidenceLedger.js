'use strict';

const { Contract } = require('fabric-contract-api');

/**
 * SPEMACS evidence integrity ledger.
 *
 * Design notes, because two obvious approaches are wrong here:
 *
 * 1. No block counter, and no previous-hash chain of our own. Fabric blocks
 *    already hash-chain, and every key carries a version history reachable
 *    through GetHistoryForKey. Re-implementing a chain inside the chaincode
 *    would add nothing, and a read-then-increment "head" key is the classic
 *    Fabric hotspot: two transactions in the same block read the same version
 *    and the second fails validation with MVCC_READ_CONFLICT. Records are keyed
 *    by evidence id instead, which has no shared counter to contend on.
 *
 * 2. Nothing here reads the wall clock or generates randomness. Every endorsing
 *    peer executes this independently and the read/write sets must match byte
 *    for byte, so timestamps arrive as arguments (fixed before endorsement) and
 *    anything we timestamp ourselves comes from the transaction, not Date.now().
 *
 * Idempotency: every write carries an anchorId derived by the caller from the
 * payload. Submitting one twice is a no-op that reports the original txId, so
 * the outbox worker can retry a delivery it is unsure about without creating a
 * second anchor.
 *
 * Scope: this attests that a recorded digest and custody history have not
 * changed. It does not attest that the underlying evidence is truthful.
 */
class EvidenceLedger extends Contract {

    constructor() {
        super('EvidenceLedger');
    }

    // ---- key helpers ----------------------------------------------------

    _anchorKey(ctx, evidenceId) {
        return ctx.stub.createCompositeKey('anchor', [evidenceId]);
    }

    _dedupeKey(ctx, anchorId) {
        return ctx.stub.createCompositeKey('seen', [anchorId]);
    }

    _txTime(ctx) {
        const ts = ctx.stub.getTxTimestamp();
        // seconds may arrive as a Long wrapper; normalise before arithmetic.
        const raw = ts.seconds;
        const seconds = Number(raw && raw.toString ? raw.toString() : raw);
        const millis = Math.floor((ts.nanos || 0) / 1000000);
        return new Date(seconds * 1000 + millis).toISOString();
    }

    _requireFields(payload, fields) {
        const missing = fields.filter(function (f) { return !payload[f]; });
        if (missing.length) {
            throw new Error('Missing required field(s): ' + missing.join(', '));
        }
    }

    async _alreadySeen(ctx, anchorId) {
        const raw = await ctx.stub.getState(this._dedupeKey(ctx, anchorId));
        if (!raw || raw.length === 0) {
            return null;
        }
        return JSON.parse(raw.toString());
    }

    async _markSeen(ctx, anchorId, evidenceId) {
        const record = {
            anchorId: anchorId,
            evidenceId: evidenceId,
            txId: ctx.stub.getTxID(),
            recordedAt: this._txTime(ctx)
        };
        await ctx.stub.putState(
            this._dedupeKey(ctx, anchorId),
            Buffer.from(JSON.stringify(record))
        );
        return record;
    }

    // ---- writes ---------------------------------------------------------

    /**
     * Seal a new evidence artifact, or re-seal an existing id.
     * payload: { evidence_id, case_id, title, sha256, custodian, sealed_at }
     */
    async SealEvidence(ctx, anchorId, payloadJson) {
        return this._write(ctx, anchorId, 'EVIDENCE_SEALED', payloadJson,
            ['evidence_id', 'case_id', 'sha256']);
    }

    /**
     * Record a custody action against existing evidence.
     * payload: { evidence_id, case_id, action, sha256, actor, occurred_at, details }
     */
    async RecordCustody(ctx, anchorId, payloadJson) {
        return this._write(ctx, anchorId, 'CUSTODY', payloadJson,
            ['evidence_id', 'action', 'actor']);
    }

    /**
     * Record the outcome of an integrity audit.
     * payload: { evidence_id, case_id, sha256, result, actor, occurred_at }
     */
    async RecordAudit(ctx, anchorId, payloadJson) {
        return this._write(ctx, anchorId, 'INTEGRITY_AUDIT', payloadJson,
            ['evidence_id', 'result', 'actor']);
    }

    async _write(ctx, anchorId, kind, payloadJson, required) {
        if (!anchorId) {
            throw new Error('anchorId is required; it is the idempotency key.');
        }

        const seen = await this._alreadySeen(ctx, anchorId);
        if (seen) {
            // Deliberately not an error. A retried outbox delivery lands here,
            // and it should reconcile rather than fail.
            return JSON.stringify({
                anchorId: anchorId,
                duplicate: true,
                txId: seen.txId,
                detail: 'Anchor already committed; no second record written.'
            });
        }

        let payload;
        try {
            payload = JSON.parse(payloadJson);
        } catch (err) {
            throw new Error('payload is not valid JSON: ' + err.message);
        }
        this._requireFields(payload, required);

        const evidenceId = payload.evidence_id;
        const key = this._anchorKey(ctx, evidenceId);
        const existingRaw = await ctx.stub.getState(key);
        const existing = existingRaw && existingRaw.length
            ? JSON.parse(existingRaw.toString())
            : null;

        // Re-sealing an id under a different digest is a real event, not an
        // error -- re-registration happens. It is written as a new version so
        // the history shows the digest changing, and who changed it.
        const record = {
            docType: 'anchor',
            evidenceId: evidenceId,
            caseId: payload.case_id || (existing ? existing.caseId : null),
            kind: kind,
            action: payload.action || kind,
            sha256: payload.sha256 || (existing ? existing.sha256 : null),
            actor: payload.actor || payload.custodian || 'unknown',
            occurredAt: payload.occurred_at || payload.sealed_at || this._txTime(ctx),
            details: payload.details || {},
            anchorId: anchorId,
            txId: ctx.stub.getTxID(),
            recordedAt: this._txTime(ctx),
            sealCount: existing ? (existing.sealCount || 0) + 1 : 1
        };

        await ctx.stub.putState(key, Buffer.from(JSON.stringify(record)));
        await this._markSeen(ctx, anchorId, evidenceId);

        ctx.stub.setEvent('AnchorRecorded', Buffer.from(JSON.stringify({
            evidenceId: evidenceId,
            kind: kind,
            anchorId: anchorId,
            sha256: record.sha256
        })));

        return JSON.stringify({
            anchorId: anchorId,
            duplicate: false,
            txId: record.txId,
            evidenceId: evidenceId,
            recordedAt: record.recordedAt,
            detail: kind + ' anchored for ' + evidenceId + '.'
        });
    }

    // ---- reads ----------------------------------------------------------

    /** Latest anchor for one evidence item. */
    async GetAnchor(ctx, evidenceId) {
        const raw = await ctx.stub.getState(this._anchorKey(ctx, evidenceId));
        if (!raw || raw.length === 0) {
            throw new Error('No anchor on the ledger for ' + evidenceId + '.');
        }
        return raw.toString();
    }

    /** Whether an anchor exists at all, without throwing. */
    async AnchorExists(ctx, evidenceId) {
        const raw = await ctx.stub.getState(this._anchorKey(ctx, evidenceId));
        return JSON.stringify({ exists: !!(raw && raw.length) });
    }

    /**
     * Every committed version of this evidence key, oldest first. This is the
     * custody trail, provided by the platform rather than reconstructed by us.
     */
    async GetAnchorHistory(ctx, evidenceId) {
        const iterator = await ctx.stub.getHistoryForKey(this._anchorKey(ctx, evidenceId));
        const history = [];
        let result = await iterator.next();
        while (!result.done) {
            const entry = result.value;
            let value = null;
            if (entry.value && entry.value.length) {
                try {
                    value = JSON.parse(entry.value.toString());
                } catch (err) {
                    value = entry.value.toString();
                }
            }
            let timestamp = null;
            if (entry.timestamp) {
                const raw = entry.timestamp.seconds;
                const seconds = Number(raw && raw.toString ? raw.toString() : raw);
                timestamp = new Date(seconds * 1000).toISOString();
            }
            history.push({
                txId: entry.txId,
                timestamp: timestamp,
                isDelete: !!entry.isDelete,
                value: value
            });
            result = await iterator.next();
        }
        await iterator.close();
        return JSON.stringify({ evidenceId: evidenceId, history: history });
    }

    /**
     * Does the ledger hold this digest for this evidence item? The question a
     * verification endpoint actually asks.
     */
    async VerifyAnchor(ctx, evidenceId, sha256) {
        const raw = await ctx.stub.getState(this._anchorKey(ctx, evidenceId));
        if (!raw || raw.length === 0) {
            return JSON.stringify({
                match: false,
                anchoredSha256: null,
                detail: 'No anchor on the ledger for ' + evidenceId + '.'
            });
        }
        const record = JSON.parse(raw.toString());
        const match = !!record.sha256 && record.sha256 === sha256;
        return JSON.stringify({
            match: match,
            anchoredSha256: record.sha256,
            txId: record.txId,
            recordedAt: record.recordedAt,
            detail: match
                ? 'Digest matches the value anchored on the ledger.'
                : 'Digest does NOT match the value anchored on the ledger.'
        });
    }

    /** All anchors for one case, by composite-key range rather than a rich query. */
    async QueryByCase(ctx, caseId) {
        const iterator = await ctx.stub.getStateByPartialCompositeKey('anchor', []);
        const matches = [];
        let result = await iterator.next();
        while (!result.done) {
            if (result.value && result.value.value && result.value.value.length) {
                try {
                    const record = JSON.parse(result.value.value.toString());
                    if (record.caseId === caseId) {
                        matches.push(record);
                    }
                } catch (err) {
                    // A key we cannot parse is not a reason to fail the query.
                }
            }
            result = await iterator.next();
        }
        await iterator.close();
        return JSON.stringify({ caseId: caseId, count: matches.length, anchors: matches });
    }
}

module.exports = EvidenceLedger;
