'use strict';

/**
 * Dev server: the gateway's HTTP contract, backed by the real chaincode class
 * running against an in-memory stub.
 *
 * ---------------------------------------------------------------------------
 * THIS IS NOT A LEDGER. There is no consensus, no endorsement by a second
 * organisation, no ordering service, and state is lost when the process exits.
 * It proves that the contract logic and the backend integration are correct.
 * It proves NOTHING about distributed trust or tamper resistance.
 * ---------------------------------------------------------------------------
 *
 * Every response carries mode:"stub", and the SPEMACS backend surfaces that
 * wherever it reports ledger state, so a stub can never be mistaken for a real
 * anchor in the UI, in a court dossier, or in a demo.
 *
 * Use it to develop the integration before Docker and WSL2 are installed, then
 * run fabric/gateway/server.js against the real network.
 */

const http = require('node:http');
const EvidenceLedger = require('../lib/evidenceLedger');
const { MockStub } = require('./mockStub');

const PORT = Number(process.env.GATEWAY_PORT || 7090);
const HOST = process.env.GATEWAY_HOST || '127.0.0.1';
const TOKEN = process.env.GATEWAY_TOKEN || '';

const contract = new EvidenceLedger();
const stub = new MockStub();
const ctx = { stub };

function send(res, status, body) {
    const payload = JSON.stringify({ ...body, mode: 'stub' });
    res.writeHead(status, {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
    });
    res.end(payload);
}

function authorized(req) {
    if (!TOKEN) {
        return true;
    }
    const header = req.headers.authorization || '';
    return header === `Bearer ${TOKEN}`;
}

function readBody(req) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        req.on('data', (c) => chunks.push(c));
        req.on('end', () => {
            const raw = Buffer.concat(chunks).toString('utf8');
            if (!raw) {
                resolve({});
                return;
            }
            try {
                resolve(JSON.parse(raw));
            } catch (err) {
                reject(new Error('Body is not valid JSON.'));
            }
        });
        req.on('error', reject);
    });
}

function transactionFor(action) {
    switch (action) {
        case 'EVIDENCE_SEALED': return 'SealEvidence';
        case 'INTEGRITY_AUDIT': return 'RecordAudit';
        default: return 'RecordCustody';
    }
}

async function route(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const segments = url.pathname.split('/').filter(Boolean);

    if (req.method === 'GET' && url.pathname === '/health') {
        send(res, 200, {
            ready: true,
            detail: 'STUB LEDGER - in-memory, no consensus, no second organisation. '
                  + 'Contract logic only. Not a tamper-resistant record.',
            channel: 'stub',
            chaincode: 'spemacs-ledger',
            mspId: 'StubMSP',
            anchors: stub.state.size
        });
        return;
    }

    if (!authorized(req)) {
        send(res, 401, { error: 'Unauthorized.' });
        return;
    }

    if (req.method === 'POST' && url.pathname === '/anchors') {
        const { anchorId, action, payload } = await readBody(req);
        if (!anchorId || !payload) {
            send(res, 400, { error: 'anchorId and payload are required.' });
            return;
        }
        stub.newTx();
        const fn = transactionFor(action || 'CUSTODY');
        const body = JSON.stringify({ ...payload, action: payload.action || action });
        const result = JSON.parse(await contract[fn](ctx, anchorId, body));
        send(res, result.duplicate ? 409 : 201, {
            txId: result.txId,
            duplicate: !!result.duplicate,
            evidenceId: result.evidenceId || payload.evidence_id,
            detail: result.detail
        });
        return;
    }

    if (req.method === 'POST' && url.pathname === '/anchors/verify') {
        const { evidenceId, sha256 } = await readBody(req);
        if (!evidenceId || !sha256) {
            send(res, 400, { error: 'evidenceId and sha256 are required.' });
            return;
        }
        send(res, 200, JSON.parse(await contract.VerifyAnchor(ctx, evidenceId, sha256)));
        return;
    }

    if (req.method === 'GET' && segments[0] === 'anchors' && segments[1]) {
        const evidenceId = decodeURIComponent(segments[1]);
        if (segments[2] === 'history') {
            send(res, 200, JSON.parse(await contract.GetAnchorHistory(ctx, evidenceId)));
            return;
        }
        const exists = JSON.parse(await contract.AnchorExists(ctx, evidenceId));
        if (!exists.exists) {
            send(res, 404, { error: `No anchor on the ledger for ${evidenceId}.` });
            return;
        }
        send(res, 200, JSON.parse(await contract.GetAnchor(ctx, evidenceId)));
        return;
    }

    if (req.method === 'GET' && segments[0] === 'cases' && segments[1] && segments[2] === 'anchors') {
        send(res, 200, JSON.parse(await contract.QueryByCase(ctx, decodeURIComponent(segments[1]))));
        return;
    }

    send(res, 404, { error: 'No such route.' });
}

const server = http.createServer((req, res) => {
    route(req, res).catch((err) => {
        send(res, err.statusCode || 500, { error: err.message });
    });
});

server.listen(PORT, HOST, () => {
    console.log(`[devserver] STUB ledger on http://${HOST}:${PORT}`);
    console.log('[devserver] In-memory only. No consensus. Not a real Fabric network.');
});

process.on('SIGINT', () => { server.close(); process.exit(0); });
process.on('SIGTERM', () => { server.close(); process.exit(0); });
