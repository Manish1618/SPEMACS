'use strict';



/**

 * Contract logic tests against an in-memory stub.

 *

 * These do not need a Fabric network, Docker, or WSL. They exercise the parts

 * that are ours -- idempotency, required fields, version history, digest

 * verification -- so the logic is known good before it ever reaches a peer.

 *

 * Run: npm test   (from fabric/chaincode/spemacs-ledger)

 */



const test = require('node:test');

const assert = require('node:assert');



const EvidenceLedger = require('../lib/evidenceLedger');



const { MockStub } = require('../dev/mockStub');

function newCtx() {

    const stub = new MockStub();

    return { stub: stub };

}



const SEAL = {

    evidence_id: 'EVID-CDR-01',

    case_id: 'CASE-2024-8812',

    title: 'Call detail records, March',

    sha256: 'a'.repeat(64),

    custodian: 'insp.sharma',

    sealed_at: '2026-09-13T10:00:00Z'

};



test('SealEvidence writes an anchor and emits an event', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();



    const raw = await contract.SealEvidence(ctx, 'anchor-1', JSON.stringify(SEAL));

    const result = JSON.parse(raw);



    assert.strictEqual(result.duplicate, false);

    assert.strictEqual(result.evidenceId, 'EVID-CDR-01');

    assert.strictEqual(ctx.stub.events.length, 1);

    assert.strictEqual(ctx.stub.events[0].name, 'AnchorRecorded');



    const anchor = JSON.parse(await contract.GetAnchor(ctx, 'EVID-CDR-01'));

    assert.strictEqual(anchor.sha256, SEAL.sha256);

    assert.strictEqual(anchor.caseId, 'CASE-2024-8812');

    assert.strictEqual(anchor.sealCount, 1);

});



test('resubmitting the same anchorId is a no-op that reports the first txId', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();



    ctx.stub.newTx();

    const first = JSON.parse(await contract.SealEvidence(ctx, 'anchor-1', JSON.stringify(SEAL)));



    ctx.stub.newTx();

    const second = JSON.parse(await contract.SealEvidence(ctx, 'anchor-1', JSON.stringify(SEAL)));



    assert.strictEqual(second.duplicate, true);

    assert.strictEqual(second.txId, first.txId, 'duplicate must report the original txId');

    // One anchor write plus one dedupe marker, and no second event.

    assert.strictEqual(ctx.stub.events.length, 1);

});



test('a different anchorId for the same evidence writes a new version', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();



    ctx.stub.newTx();

    await contract.SealEvidence(ctx, 'anchor-1', JSON.stringify(SEAL));



    ctx.stub.newTx();

    await contract.RecordCustody(ctx, 'anchor-2', JSON.stringify({

        evidence_id: 'EVID-CDR-01',

        case_id: 'CASE-2024-8812',

        action: 'TRANSFER',

        sha256: SEAL.sha256,

        actor: 'insp.rao',

        occurred_at: '2026-09-13T11:00:00Z',

        details: { to_custodian: 'forensics.lab' }

    }));



    const history = JSON.parse(await contract.GetAnchorHistory(ctx, 'EVID-CDR-01'));

    assert.strictEqual(history.history.length, 2, 'both versions must be in history');

    assert.strictEqual(history.history[0].value.kind, 'EVIDENCE_SEALED');

    assert.strictEqual(history.history[1].value.kind, 'CUSTODY');

    // A custody event is not a seal, so the seal count must not advance.
    assert.strictEqual(history.history[1].value.sealCount, 1);
    // ...and the attested digest must survive it untouched.
    assert.strictEqual(history.history[1].value.sha256, SEAL.sha256);

});



test('VerifyAnchor distinguishes a matching digest from a tampered one', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();

    await contract.SealEvidence(ctx, 'anchor-1', JSON.stringify(SEAL));



    const good = JSON.parse(await contract.VerifyAnchor(ctx, 'EVID-CDR-01', SEAL.sha256));

    assert.strictEqual(good.match, true);



    const bad = JSON.parse(await contract.VerifyAnchor(ctx, 'EVID-CDR-01', 'b'.repeat(64)));

    assert.strictEqual(bad.match, false);

    assert.strictEqual(bad.anchoredSha256, SEAL.sha256);

});



test('VerifyAnchor on unknown evidence reports no anchor rather than throwing', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    const result = JSON.parse(await contract.VerifyAnchor(ctx, 'EVID-NOPE', 'c'.repeat(64)));

    assert.strictEqual(result.match, false);

    assert.strictEqual(result.anchoredSha256, null);

});



test('missing required fields are rejected', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();



    await assert.rejects(

        () => contract.SealEvidence(ctx, 'anchor-x', JSON.stringify({

            evidence_id: 'EVID-CDR-02'

            // case_id and sha256 absent

        })),

        /Missing required field\(s\): case_id, sha256/

    );

});



test('malformed payload JSON is rejected with a usable message', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();

    await assert.rejects(

        () => contract.SealEvidence(ctx, 'anchor-y', '{not json'),

        /payload is not valid JSON/

    );

});



test('an empty anchorId is rejected', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();

    await assert.rejects(

        () => contract.SealEvidence(ctx, '', JSON.stringify(SEAL)),

        /anchorId is required/

    );

});



test('QueryByCase returns only that case', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();



    ctx.stub.newTx();

    await contract.SealEvidence(ctx, 'a1', JSON.stringify(SEAL));



    ctx.stub.newTx();

    await contract.SealEvidence(ctx, 'a2', JSON.stringify({

        evidence_id: 'EVID-FIN-09',

        case_id: 'CASE-2023-1104',

        sha256: 'd'.repeat(64),

        custodian: 'insp.rao'

    }));



    const mine = JSON.parse(await contract.QueryByCase(ctx, 'CASE-2024-8812'));

    assert.strictEqual(mine.count, 1);

    assert.strictEqual(mine.anchors[0].evidenceId, 'EVID-CDR-01');

});



test('AnchorExists does not throw for unknown evidence', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    const absent = JSON.parse(await contract.AnchorExists(ctx, 'EVID-NOPE'));

    assert.strictEqual(absent.exists, false);

});



test('timestamps come from the transaction, never the wall clock', async () => {

    const contract = new EvidenceLedger();

    const ctx = newCtx();

    ctx.stub.newTx();



    // No sealed_at supplied, so the contract must fall back to tx time.

    await contract.RecordAudit(ctx, 'audit-1', JSON.stringify({

        evidence_id: 'EVID-CDR-01',

        case_id: 'CASE-2024-8812',

        sha256: SEAL.sha256,

        result: 'VERIFIED',

        actor: 'system'

    }));



    const anchor = JSON.parse(await contract.GetAnchor(ctx, 'EVID-CDR-01'));

    // 1757000000 + txCounter(1) -> deterministic, not Date.now()

    assert.strictEqual(anchor.recordedAt, new Date(1757000001 * 1000).toISOString());

});


test('an integrity audit cannot overwrite the attested digest', async () => {
    // The regression this guards: an audit carries the digest it OBSERVED. During
    // a tamper event that is the altered value. If it overwrote the anchor, the
    // ledger would end up agreeing with the tampered artifact -- and the anchor
    // would attest nothing at all.
    const contract = new EvidenceLedger();
    const ctx = newCtx();

    ctx.stub.newTx();
    await contract.SealEvidence(ctx, 'seal-1', JSON.stringify(SEAL));

    const tamperedDigest = '9'.repeat(64);
    ctx.stub.newTx();
    await contract.RecordAudit(ctx, 'audit-1', JSON.stringify({
        evidence_id: 'EVID-CDR-01',
        case_id: 'CASE-2024-8812',
        sha256: tamperedDigest,
        result: 'TAMPER_DETECTED',
        actor: 'insp.rao'
    }));

    const anchor = JSON.parse(await contract.GetAnchor(ctx, 'EVID-CDR-01'));
    assert.strictEqual(anchor.sha256, SEAL.sha256, 'attested digest must be unchanged');
    assert.strictEqual(anchor.observedSha256, tamperedDigest, 'what the audit saw is kept separately');

    // And the ledger must still disagree with the tampered value.
    const check = JSON.parse(await contract.VerifyAnchor(ctx, 'EVID-CDR-01', tamperedDigest));
    assert.strictEqual(check.match, false);

    // While still agreeing with the real one, so a restore verifies clean.
    const good = JSON.parse(await contract.VerifyAnchor(ctx, 'EVID-CDR-01', SEAL.sha256));
    assert.strictEqual(good.match, true, 'a restored artifact must verify against the ledger');
});

test('a custody transfer does not move the attested digest either', async () => {
    const contract = new EvidenceLedger();
    const ctx = newCtx();
    ctx.stub.newTx();
    await contract.SealEvidence(ctx, 'seal-1', JSON.stringify(SEAL));

    ctx.stub.newTx();
    await contract.RecordCustody(ctx, 'move-1', JSON.stringify({
        evidence_id: 'EVID-CDR-01',
        action: 'TRANSFER',
        sha256: 'f'.repeat(64),
        actor: 'forensics.lab'
    }));

    const anchor = JSON.parse(await contract.GetAnchor(ctx, 'EVID-CDR-01'));
    assert.strictEqual(anchor.sha256, SEAL.sha256);
});

test('a deliberate re-seal DOES move the attested digest', async () => {
    // Re-registration is legitimate: the new digest becomes the attested one,
    // and the history records that it changed.
    const contract = new EvidenceLedger();
    const ctx = newCtx();
    ctx.stub.newTx();
    await contract.SealEvidence(ctx, 'seal-1', JSON.stringify(SEAL));

    const reissued = 'c'.repeat(64);
    ctx.stub.newTx();
    await contract.SealEvidence(ctx, 'seal-2', JSON.stringify({
        ...SEAL,
        sha256: reissued
    }));

    const anchor = JSON.parse(await contract.GetAnchor(ctx, 'EVID-CDR-01'));
    assert.strictEqual(anchor.sha256, reissued);
    assert.strictEqual(anchor.sealCount, 2);
});
