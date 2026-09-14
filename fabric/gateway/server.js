'use strict';

/**
 * SPEMACS Fabric gateway sidecar.
 *
 * Why this process exists: Fabric's v2.4+ Gateway SDKs are published for Go,
 * Node and Java. The SPEMACS API is Python, so rather than hand-rolling gRPC and
 * endorsement handling against fabric-protos, the supported Node SDK runs here
 * and offers a narrow HTTP face to the backend.
 *
 * This is the only process holding Fabric identity material. It listens on
 * loopback by default and requires a bearer token, because anything that can
 * call it can write to the ledger.
 *
 * It never exits on a connection failure. If the network is down it keeps
 * serving /health with ready:false, so the backend can degrade to its local
 * ledger and queue anchors instead of failing evidence writes.
 *
 * No framework: five routes do not justify a dependency tree. The only runtime
 * dependencies are the Fabric gateway SDK and grpc-js.
 */

const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

const grpc = require('@grpc/grpc-js');
const { connect, signers } = require('@hyperledger/fabric-gateway');

// ---- configuration ------------------------------------------------------

const config = {
    port: Number(process.env.GATEWAY_PORT || 7090),
    host: process.env.GATEWAY_HOST || '127.0.0.1',
    token: process.env.GATEWAY_TOKEN || '',

    channel: process.env.FABRIC_CHANNEL || 'spemacs',
    chaincode: process.env.FABRIC_CHAINCODE || 'spemacs-ledger',
    contract: process.env.FABRIC_CONTRACT || 'EvidenceLedger',

    mspId: process.env.FABRIC_MSP_ID || 'Org1MSP',
    peerEndpoint: process.env.FABRIC_PEER_ENDPOINT || 'localhost:7051',
    peerHostAlias: process.env.FABRIC_PEER_HOST_ALIAS || 'peer0.org1.example.com',

    tlsCertPath: process.env.FABRIC_TLS_CERT_PATH || '',
    certPath: process.env.FABRIC_CERT_PATH || '',
    keyDir: process.env.FABRIC_KEY_DIR || ''
};

let gateway = null;
let client = null;
let contract = null;
let lastError = 'not connected yet';

// ---- Fabric connection --------------------------------------------------

async function firstFileIn(dir) {
    const entries = await fs.readdir(dir);
    if (!entries.length) {
        throw new Error(`No key file found in ${dir}`);
    }
    return path.join(dir, entries[0]);
}

async function newIdentity() {
    const credentials = await fs.readFile(config.certPath);
    return { mspId: config.mspId, credentials };
}

async function newSigner() {
    const keyPath = await firstFileIn(config.keyDir);
    const privateKeyPem = await fs.readFile(keyPath);
    const privateKey = crypto.createPrivateKey(privateKeyPem);
    return signers.newPrivateKeySigner(privateKey);
}

async function newGrpcConnection() {
    const tlsRootCert = await fs.readFile(config.tlsCertPath);
    const credentials = grpc.credentials.createSsl(tlsRootCert);
    return new grpc.Client(config.peerEndpoint, credentials, {
        'grpc.ssl_target_name_override': config.peerHostAlias
    });
}

async function connectToFabric() {
    for (const [name, value] of Object.entries({
        FABRIC_TLS_CERT_PATH: config.tlsCertPath,
        FABRIC_CERT_PATH: config.certPath,
        FABRIC_KEY_DIR: config.keyDir
    })) {
        if (!value) {
            throw new Error(`${name} is not set. Run fabric/scripts/env.sh first.`);
        }
    }

    client = await newGrpcConnection();
    gateway = connect({
        client,
        identity: await newIdentity(),
        signer: await newSigner(),
        // Endorsement takes longest: it waits on every org in the policy.
        evaluateOptions: () => ({ deadline: Date.now() + 15000 }),
        endorseOptions: () => ({ deadline: Date.now() + 30000 }),
        submitOptions: () => ({ deadline: Date.now() + 15000 }),
        commitStatusOptions: () => ({ deadline: Date.now() + 60000 })
    });

    const network = gateway.getNetwork(config.channel);
    contract = network.getContract(config.chaincode, config.contract);
    lastError = null;
    console.log(
        `[gateway] connected: msp=${config.mspId} peer=${config.peerEndpoint} ` +
        `channel=${config.channel} chaincode=${config.chaincode}`
    );
}

async function tryConnect() {
    try {
        await connectToFabric();
        return true;
    } catch (err) {
        lastError = err.message;
        contract = null;
        console.warn(`[gateway] not connected: ${err.message}`);
        return false;
    }
}

/** Reconnect lazily, so the sidecar recovers without a restart. */
async function ensureContract() {
    if (contract) {
        return contract;
    }
    await tryConnect();
    return contract;
}

// ---- chaincode calls ----------------------------------------------------

const utf8 = new TextDecoder();

/** Which chaincode function handles which anchor action. */
function transactionFor(action) {
    switch (action) {
        case 'EVIDENCE_SEALED':
            return 'SealEvidence';
        case 'INTEGRITY_AUDIT':
            return 'RecordAudit';
        default:
            // TRANSFER, ACCESS, COLLECTED and friends are all custody events.
            return 'RecordCustody';
    }
}

async function submitAnchor(anchorId, action, payload) {
    const active = await ensureContract();
    if (!active) {
        const err = new Error(lastError || 'Fabric gateway is not connected.');
        err.statusCode = 503;
        throw err;
    }

    const fn = transactionFor(action);
    const body = JSON.stringify({ ...payload, action: payload.action || action });

    const resultBytes = await active.submitTransaction(fn, anchorId, body);
    const result = JSON.parse(utf8.decode(resultBytes));

    // The chaincode reports a replayed anchor rather than failing, so the
    // backend's outbox can retry a delivery whose outcome it never saw.
    return {
        txId: result.txId,
        duplicate: !!result.duplicate,
        evidenceId: result.evidenceId || payload.evidence_id,
        detail: result.detail
    };
}

async function evaluate(fn, ...args) {
    const active = await ensureContract();
    if (!active) {
        const err = new Error(lastError || 'Fabric gateway is not connected.');
        err.statusCode = 503;
        throw err;
    }
    const resultBytes = await active.evaluateTransaction(fn, ...args);
    return JSON.parse(utf8.decode(resultBytes));
}

// ---- HTTP plumbing ------------------------------------------------------

function send(res, status, body) {
    const payload = JSON.stringify(body);
    res.writeHead(status, {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
    });
    res.end(payload);
}

function authorized(req) {
    if (!config.token) {
        return true; // no token configured: loopback-only deployments
    }
    const header = req.headers.authorization || '';
    const supplied = header.startsWith('Bearer ') ? header.slice(7) : '';
    if (supplied.length !== config.token.length) {
        return false;
    }
    return crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(config.token));
}

function readBody(req) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        let size = 0;
        req.on('data', (chunk) => {
            size += chunk.length;
            if (size > 1_000_000) {
                reject(new Error('Request body too large.'));
                req.destroy();
                return;
            }
            chunks.push(chunk);
        });
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

// ---- routes -------------------------------------------------------------

async function route(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const segments = url.pathname.split('/').filter(Boolean);

    if (req.method === 'GET' && url.pathname === '/health') {
        const ready = !!(await ensureContract());
        send(res, 200, {
            ready,
            detail: ready ? 'Gateway connected to the channel.' : (lastError || 'Not connected.'),
            channel: config.channel,
            chaincode: config.chaincode,
            mspId: config.mspId,
            peer: config.peerEndpoint
        });
        return;
    }

    if (!authorized(req)) {
        send(res, 401, { error: 'Unauthorized.' });
        return;
    }

    // POST /anchors
    if (req.method === 'POST' && url.pathname === '/anchors') {
        const body = await readBody(req);
        const { anchorId, action, payload } = body;
        if (!anchorId || !payload) {
            send(res, 400, { error: 'anchorId and payload are required.' });
            return;
        }
        const result = await submitAnchor(anchorId, action || 'CUSTODY', payload);
        send(res, result.duplicate ? 409 : 201, result);
        return;
    }

    // POST /anchors/verify
    if (req.method === 'POST' && url.pathname === '/anchors/verify') {
        const body = await readBody(req);
        const { evidenceId, sha256 } = body;
        if (!evidenceId || !sha256) {
            send(res, 400, { error: 'evidenceId and sha256 are required.' });
            return;
        }
        send(res, 200, await evaluate('VerifyAnchor', evidenceId, sha256));
        return;
    }

    // GET /anchors/:evidenceId  and  GET /anchors/:evidenceId/history
    if (req.method === 'GET' && segments[0] === 'anchors' && segments[1]) {
        const evidenceId = decodeURIComponent(segments[1]);

        if (segments[2] === 'history') {
            send(res, 200, await evaluate('GetAnchorHistory', evidenceId));
            return;
        }

        const exists = await evaluate('AnchorExists', evidenceId);
        if (!exists.exists) {
            send(res, 404, { error: `No anchor on the ledger for ${evidenceId}.` });
            return;
        }
        send(res, 200, await evaluate('GetAnchor', evidenceId));
        return;
    }

    // GET /cases/:caseId/anchors
    if (req.method === 'GET' && segments[0] === 'cases' && segments[1] && segments[2] === 'anchors') {
        send(res, 200, await evaluate('QueryByCase', decodeURIComponent(segments[1])));
        return;
    }

    send(res, 404, { error: 'No such route.' });
}

const server = http.createServer((req, res) => {
    route(req, res).catch((err) => {
        const status = err.statusCode || 500;
        if (status >= 500) {
            console.error(`[gateway] ${req.method} ${req.url} -> ${status}: ${err.message}`);
            // A failed submit may mean a stale connection; drop it so the next
            // call reconnects rather than failing the same way forever.
            if (status === 503) {
                contract = null;
            }
        }
        send(res, status, { error: err.message });
    });
});

server.listen(config.port, config.host, async () => {
    console.log(`[gateway] listening on http://${config.host}:${config.port}`);
    if (!config.token) {
        console.warn('[gateway] GATEWAY_TOKEN is not set: any local process can write to the ledger.');
    }
    await tryConnect();
});

function shutdown() {
    console.log('[gateway] shutting down');
    server.close();
    if (gateway) {
        gateway.close();
    }
    if (client) {
        client.close();
    }
    process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
