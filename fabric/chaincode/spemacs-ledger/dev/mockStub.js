'use strict';

/**
 * In-memory ChaincodeStub, good enough for this contract.
 *
 * Shared by the contract tests and the dev server. It implements the stub
 * surface EvidenceLedger actually touches: composite keys, state, key history,
 * partial-key range scans, transaction identity and events.
 *
 * It is NOT a Fabric network. There is no consensus, no endorsement, no
 * ordering, and no second organisation -- so it proves contract logic and
 * nothing about distributed trust.
 */

const SEP = '\u0000';

class MockStub {
    constructor() {
        this.state = new Map();
        this.history = new Map();
        this.events = [];
        this.txCounter = 0;
        this.txId = 'tx-0';
    }

    newTx(txId) {
        this.txCounter += 1;
        this.txId = txId || 'tx-' + this.txCounter;
        return this.txId;
    }

    createCompositeKey(objectType, attributes) {
        return SEP + objectType + SEP + attributes.join(SEP) + SEP;
    }

    getTxID() {
        return this.txId;
    }

    getTxTimestamp() {
        return { seconds: 1757000000 + this.txCounter, nanos: 0 };
    }

    async getState(key) {
        const value = this.state.get(key);
        return value ? Buffer.from(value) : Buffer.alloc(0);
    }

    async putState(key, value) {
        const asString = value.toString();
        this.state.set(key, asString);
        if (!this.history.has(key)) {
            this.history.set(key, []);
        }
        this.history.get(key).push({
            txId: this.txId,
            timestamp: { seconds: 1757000000 + this.txCounter, nanos: 0 },
            value: Buffer.from(asString),
            isDelete: false
        });
    }

    setEvent(name, payload) {
        this.events.push({ name: name, payload: JSON.parse(payload.toString()) });
    }

    async getHistoryForKey(key) {
        return makeIterator((this.history.get(key) || []).slice());
    }

    async getStateByPartialCompositeKey(objectType, attributes) {
        const prefix = SEP + objectType + SEP + attributes.join(SEP);
        const entries = [];
        for (const [key, value] of this.state.entries()) {
            if (key.startsWith(prefix)) {
                entries.push({ key: key, value: Buffer.from(value) });
            }
        }
        return makeIterator(entries);
    }
}

function makeIterator(items) {
    let index = 0;
    return {
        async next() {
            if (index < items.length) {
                const value = items[index];
                index += 1;
                return { done: false, value: value };
            }
            return { done: true, value: null };
        },
        async close() { /* nothing to release */ }
    };
}

module.exports = { MockStub, makeIterator };
