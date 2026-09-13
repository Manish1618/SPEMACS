import React, { useState, useEffect } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, RefreshCw, Hash, Cpu, Lock, Link2, Link2Off, FlaskConical } from 'lucide-react';
import type { AnchoringStatus, EvidenceItem, FabricAnchor } from '../../types';
import { api } from '../../lib/api';

interface EvidenceVaultProps {
  activeCaseId: string;
}

/** Header pill: is anchoring on, is the ledger reachable, and is it the stub? */
const AnchoringBadge: React.FC<{ status: AnchoringStatus }> = ({ status }) => {
  if (!status.enabled) {
    return (
      <span
        title={status.detail}
        className="text-[10px] bg-gray-600/20 text-gray-400 px-2 py-0.5 rounded font-mono border border-gray-600/30 flex items-center space-x-1"
      >
        <Link2Off className="w-3 h-3" />
        <span>Local ledger only</span>
      </span>
    );
  }

  if (!status.reachable) {
    return (
      <span
        title={status.detail}
        className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono border border-amber-500/30 flex items-center space-x-1"
      >
        <Link2Off className="w-3 h-3" />
        <span>Ledger unreachable</span>
      </span>
    );
  }

  // A stub answer must never look like a real anchor.
  const isStub = status.mode === 'stub' || (status.channel || '').toLowerCase() === 'stub';
  if (isStub) {
    return (
      <span
        title={status.detail}
        className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded font-mono border border-purple-500/30 flex items-center space-x-1"
      >
        <FlaskConical className="w-3 h-3" />
        <span>Stub ledger - no consensus</span>
      </span>
    );
  }

  return (
    <span
      title={status.detail}
      className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-mono border border-emerald-500/30 flex items-center space-x-1"
    >
      <Link2 className="w-3 h-3" />
      <span>Fabric {status.channel} - 2 orgs</span>
    </span>
  );
};

/** One of the two independent verdicts shown after a verification. */
const VerdictTile: React.FC<{ label: string; ok: boolean; detail: string; muted?: boolean }> = ({
  label,
  ok,
  detail,
  muted = false,
}) => (
  <div
    className={`p-2.5 rounded border ${
      muted
        ? 'bg-dark-900/60 border-gray-700 text-gray-400'
        : ok
        ? 'bg-emerald-950/50 border-emerald-600/40 text-emerald-200'
        : 'bg-red-950/50 border-red-600/50 text-red-200'
    }`}
  >
    <div className="text-[10px] uppercase tracking-wider font-bold opacity-80">{label}</div>
    <div className="text-xs font-bold mt-0.5">{muted ? 'Not consulted' : ok ? 'MATCH' : 'MISMATCH'}</div>
    <div className="text-[10px] mt-0.5 opacity-80 leading-snug">{detail}</div>
  </div>
);

const FabricVerdictTile: React.FC<{ verification?: any }> = ({ verification }) => {
  if (!verification || !verification.checked) {
    return (
      <VerdictTile
        label="Permissioned ledger"
        ok={false}
        muted
        detail={verification?.detail || 'Anchoring is disabled for this deployment.'}
      />
    );
  }
  return (
    <VerdictTile
      label="Permissioned ledger"
      ok={!!verification.match}
      detail={
        verification.match
          ? 'Digest matches the anchor held outside this database'
          : `Ledger holds ${String(verification.anchored_sha256 || '').slice(0, 16)}...`
      }
    />
  );
};

/** What chaincode holds for this item, and how it got there. */
const FabricAnchorPanel: React.FC<{
  anchor: FabricAnchor | null;
  status: AnchoringStatus | null;
}> = ({ anchor, status }) => {
  if (!status?.enabled) {
    return (
      <div className="p-3.5 bg-dark-800/60 rounded-xl border border-gray-800 border-dashed">
        <div className="flex items-center space-x-1.5 text-[10px] text-gray-500 font-bold uppercase tracking-wider">
          <Link2Off className="w-3.5 h-3.5" />
          <span>Permissioned Ledger Anchor</span>
        </div>
        <p className="text-[11px] text-gray-500 mt-1 leading-snug">
          Anchoring is switched off. Integrity rests on the local hash chain alone, which is
          stored in the same database it attests. Start the ledger and set FABRIC_ENABLED=true
          to anchor independently.
        </p>
      </div>
    );
  }

  if (!anchor || !anchor.anchor) {
    return (
      <div className="p-3.5 bg-dark-800 rounded-xl border border-amber-600/30">
        <div className="flex items-center space-x-1.5 text-[10px] text-amber-400 font-bold uppercase tracking-wider">
          <Link2Off className="w-3.5 h-3.5" />
          <span>Permissioned Ledger Anchor</span>
        </div>
        <p className="text-[11px] text-gray-400 mt-1">
          {anchor?.detail || 'No anchor on the ledger yet for this item.'}
          {!!anchor?.unanchored_entries && ` ${anchor.unanchored_entries} entr(ies) still queued.`}
        </p>
      </div>
    );
  }

  const record = anchor.anchor;
  const verified = anchor.verification?.match;

  return (
    <div className="p-3.5 bg-dark-800 rounded-xl border border-gray-800 space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5 text-[10px] text-gray-400 font-bold uppercase tracking-wider">
          <Link2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Permissioned Ledger Anchor</span>
        </div>
        <span className="text-[10px] font-mono text-gray-500">
          {anchor.channel} / {anchor.chaincode}
        </span>
      </div>

      <p className="text-[10px] text-gray-500 leading-snug">
        Read from chaincode, which is a separate store from the database holding this evidence
        record. A digest that matches here was not written by whoever wrote the record.
      </p>

      <div className="text-[11px] font-mono space-y-1 bg-dark-900/60 p-2.5 rounded border border-gray-800">
        <div>
          Anchored digest:{' '}
          <span className={verified ? 'text-emerald-400' : 'text-red-400 font-bold'}>
            {record.sha256}
          </span>
        </div>
        <div>Transaction: <span className="text-indigo-300">{record.txId}</span></div>
        <div>Sealed by: <span className="text-gray-300">{record.actor}</span></div>
        <div>Recorded: <span className="text-gray-300">{record.recordedAt}</span></div>
      </div>

      {anchor.history.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-1">
            Ledger version history ({anchor.history.length})
          </div>
          <div className="space-y-1">
            {anchor.history.map((h, i) => (
              <div
                key={h.txId + i}
                className="flex items-center justify-between text-[10px] font-mono bg-dark-900/40 px-2 py-1 rounded border border-gray-800/70"
              >
                <span className="text-gray-300">{h.value?.kind || 'record'}</span>
                <span className="text-gray-500 truncate mx-2">{h.txId}</span>
                <span className="text-gray-500">{h.timestamp || ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const EvidenceVault: React.FC<EvidenceVaultProps> = ({ activeCaseId }) => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [verificationResult, setVerificationResult] = useState<any | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [anchoring, setAnchoring] = useState<AnchoringStatus | null>(null);
  const [fabricAnchor, setFabricAnchor] = useState<FabricAnchor | null>(null);

  const fetchEvidence = async () => {
    try {
      const data = await api.getEvidence(activeCaseId);
      setEvidenceList(data);
      if (data.length > 0 && !selectedEvidence) {
        setSelectedEvidence(data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAnchoring = async () => {
    try {
      setAnchoring(await api.getAnchoringStatus());
    } catch (e) {
      // Anchoring status is supplementary; never break the vault over it.
      setAnchoring(null);
    }
  };

  const fetchFabricAnchor = async (evId: string) => {
    setFabricAnchor(null);
    try {
      setFabricAnchor(await api.getFabricAnchor(evId));
    } catch (e) {
      setFabricAnchor(null);
    }
  };

  useEffect(() => {
    fetchEvidence();
    fetchAnchoring();
  }, [activeCaseId]);

  useEffect(() => {
    if (selectedEvidence) {
      fetchFabricAnchor(selectedEvidence.evidence_id);
    }
  }, [selectedEvidence?.evidence_id]);

  const handleVerify = async (evId: string) => {
    setIsVerifying(true);
    setVerificationResult(null);
    try {
      const res = await api.verifyIntegrity(evId);
      setVerificationResult(res);
      fetchEvidence();
      fetchFabricAnchor(evId);
      fetchAnchoring();
    } catch (e) {
      console.error(e);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSimulateTamper = async (evId: string) => {
    setIsVerifying(true);
    try {
      const res = await api.simulateTamper(evId);
      setVerificationResult(res.verification_result);
      fetchEvidence();
      fetchFabricAnchor(evId);
    } catch (e) {
      console.error(e);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleRestoreClean = async (evId: string) => {
    setIsVerifying(true);
    try {
      const res = await api.restoreClean(evId);
      setVerificationResult(res.verification_result);
      fetchEvidence();
      fetchFabricAnchor(evId);
    } catch (e) {
      console.error(e);
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-500 to-teal-700 flex items-center justify-center shadow-lg">
            <Lock className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Cryptographic Evidence Vault & Permissioned Ledger</span>
              {anchoring && <AnchoringBadge status={anchoring} />}
            </h3>
            <p className="text-[11px] text-gray-400">
              {anchoring?.enabled && anchoring?.outbox
                ? `SHA-256 hashing, tamper detection - ${anchoring.outbox.detail}`
                : 'SHA-256 evidence hashing, tamper detection & hash-chained custody log'}
            </p>
          </div>
        </div>

        <button
          onClick={fetchEvidence}
          className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-white"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Evidence Table List */}
        <div className="w-1/3 border-r border-gray-800 overflow-y-auto p-3 space-y-2">
          {evidenceList.map((ev) => {
            const isSelected = selectedEvidence?.evidence_id === ev.evidence_id;
            const isTampered = ev.integrity_status === 'TAMPER_DETECTED';

            return (
              <div
                key={ev.evidence_id}
                onClick={() => {
                  setSelectedEvidence(ev);
                  setVerificationResult(null);
                }}
                className={`p-3 rounded-lg border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-dark-800 border-indigo-500 ring-1 ring-indigo-500/50'
                    : 'bg-dark-800/50 border-gray-800 hover:border-gray-700 hover:bg-dark-800'
                }`}
              >
                <div className="flex items-center justify-between text-[10px]">
                  <span className="font-mono text-indigo-400 font-semibold">{ev.evidence_id}</span>
                  <span className={`px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider ${
                    isTampered
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  }`}>
                    {ev.integrity_status}
                  </span>
                </div>

                <div className="text-xs font-bold text-gray-200 mt-1">{ev.title}</div>
                <div className="text-[10px] text-gray-400 mt-0.5 font-mono truncate">
                  SHA: {ev.sha256_hash.slice(0, 16)}...
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Selected Evidence Inspector & Tamper Verification */}
        {selectedEvidence ? (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Title & Actions */}
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono text-gray-400 uppercase tracking-wider">
                  {selectedEvidence.evidence_type}
                </span>
                <h2 className="text-base font-bold text-white mt-0.5">{selectedEvidence.title}</h2>
                <div className="text-xs text-gray-400 font-mono mt-0.5">ID: {selectedEvidence.evidence_id}</div>
              </div>

              {/* Demo Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleVerify(selectedEvidence.evidence_id)}
                  disabled={isVerifying}
                  className="flex items-center space-x-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1.5 rounded-lg transition-colors shadow"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Verify Integrity</span>
                </button>

                <button
                  onClick={() => handleSimulateTamper(selectedEvidence.evidence_id)}
                  disabled={isVerifying}
                  title="Simulate 1-byte alteration to test tamper alert detection"
                  className="flex items-center space-x-1.5 text-xs bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 font-semibold px-3 py-1.5 rounded-lg transition-colors"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                  <span>Simulate Tamper</span>
                </button>

                <button
                  onClick={() => handleRestoreClean(selectedEvidence.evidence_id)}
                  disabled={isVerifying}
                  className="flex items-center space-x-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 font-semibold px-3 py-1.5 rounded-lg transition-colors"
                >
                  <span>Restore Clean</span>
                </button>
              </div>
            </div>

            {/* Tamper Alert Banner if Result Exists */}
            {verificationResult && (
              <div className={`p-4 rounded-xl border ${
                verificationResult.is_valid
                  ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200'
                  : 'bg-red-950/40 border-red-500/60 text-red-200'
              }`}>
                <div className="flex items-center space-x-2 font-bold text-xs">
                  {verificationResult.is_valid ? <ShieldCheck className="w-5 h-5 text-emerald-400" /> : <ShieldAlert className="w-5 h-5 text-red-400 animate-pulse" />}
                  <span>{verificationResult.message}</span>
                </div>
                <div className="mt-2 text-[11px] font-mono space-y-1 bg-dark-900/60 p-2.5 rounded border border-gray-800">
                  <div>Stored SHA-256: <span className="text-gray-300">{verificationResult.stored_hash}</span></div>
                  <div>Live SHA-256:   <span className={verificationResult.is_valid ? "text-emerald-400" : "text-red-400 font-bold"}>{verificationResult.recalculated_hash}</span></div>
                  <div>
                    Local ledger block:{' '}
                    <span className="text-indigo-400">
                      {verificationResult.blockchain_tx_id
                        ? `${String(verificationResult.blockchain_tx_id).slice(0, 32)}...`
                        : 'not anchored locally'}
                    </span>
                  </div>
                </div>

                {/* Two independent opinions, reported separately so a reader can
                    see which guarantee is actually speaking. */}
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                  <VerdictTile
                    label="Local hash chain"
                    ok={verificationResult.is_valid}
                    detail={verificationResult.is_valid ? 'Digest matches the sealed value' : 'Digest does not match'}
                  />
                  <FabricVerdictTile verification={verificationResult.fabric_verification} />
                </div>
              </div>
            )}

            {/* Cryptographic & Blockchain Hashes Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 bg-dark-800 rounded-xl border border-gray-800 space-y-1">
                <div className="flex items-center space-x-1.5 text-[10px] text-gray-400 font-bold uppercase tracking-wider">
                  <Hash className="w-3.5 h-3.5 text-indigo-400" />
                  <span>SHA-256 Cryptographic Digest</span>
                </div>
                <div className="text-xs font-mono text-gray-200 break-all select-all">
                  {selectedEvidence.sha256_hash}
                </div>
              </div>

              <div className="p-3.5 bg-dark-800 rounded-xl border border-gray-800 space-y-1">
                <div className="flex items-center space-x-1.5 text-[10px] text-gray-400 font-bold uppercase tracking-wider">
                  <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Hash-Chained Ledger Block</span>
                </div>
                <div className="text-xs font-mono text-indigo-300 break-all select-all">
                  {selectedEvidence.blockchain_tx_id || 'Not yet anchored'}
                </div>
                <div className="text-[10px] text-gray-400 font-mono">
                  {selectedEvidence.blockchain_block_num !== null &&
                   selectedEvidence.blockchain_block_num !== undefined
                    ? `Block #${selectedEvidence.blockchain_block_num} - hash-chained, held in a store separate from this record`
                    : 'No local ledger block for this item'}
                </div>
              </div>
            </div>

            {/* What chaincode holds -- a store this database cannot write to */}
            <FabricAnchorPanel anchor={fabricAnchor} status={anchoring} />

            {/* Chain of Custody Audit Log */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider">
                Immutable Chain of Custody Audit Log ({selectedEvidence.custody_events?.length || 1})
              </h4>
              <div className="bg-dark-800 rounded-xl border border-gray-800 divide-y divide-gray-800/80">
                {(selectedEvidence.custody_events || []).map((evt, idx) => (
                  <div key={idx} className="p-3 flex items-center justify-between text-xs">
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-gray-200">{evt.action}</span>
                        {evt.tamper_detected && (
                          <span className="text-[9px] bg-red-500/20 text-red-400 px-1.5 py-0.2 rounded font-bold">
                            TAMPER FLAGGED
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-gray-400">
                        By: <span className="text-gray-300">{evt.performed_by}</span> • IP: <span className="font-mono">{evt.ip_address}</span>
                      </div>
                    </div>
                    <div className="text-[10px] text-gray-400 font-mono">
                      {new Date(evt.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-xs text-gray-500">
            Select an evidence artifact to inspect cryptographic seals and custody logs.
          </div>
        )}
      </div>
    </div>
  );
};
