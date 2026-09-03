import React, { useState, useEffect } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, RefreshCw, Hash, Cpu, Lock } from 'lucide-react';
import type { EvidenceItem } from '../../types';
import { api } from '../../lib/api';

interface EvidenceVaultProps {
  activeCaseId: string;
}

export const EvidenceVault: React.FC<EvidenceVaultProps> = ({ activeCaseId }) => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [verificationResult, setVerificationResult] = useState<any | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

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

  useEffect(() => {
    fetchEvidence();
  }, [activeCaseId]);

  const handleVerify = async (evId: string) => {
    setIsVerifying(true);
    setVerificationResult(null);
    try {
      const res = await api.verifyIntegrity(evId);
      setVerificationResult(res);
      fetchEvidence();
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
              <span>Cryptographic Evidence Vault & Blockchain Ledger</span>
              <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-mono border border-emerald-500/30">
                WORM Compliant
              </span>
            </h3>
            <p className="text-[11px] text-gray-400">SHA-256 evidence hashing, tamper detection & immutable custody log</p>
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
                  <div>Blockchain TX: <span className="text-indigo-400">{verificationResult.blockchain_tx_id || 'N/A'}</span></div>
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
                  <span>Blockchain Anchor Transaction</span>
                </div>
                <div className="text-xs font-mono text-indigo-300 break-all select-all">
                  {selectedEvidence.blockchain_tx_id || '0x44ab89c2...'}
                </div>
                <div className="text-[10px] text-gray-400 font-mono">
                  Block #{selectedEvidence.blockchain_block_num || 14200001} • Anchored at Registration
                </div>
              </div>
            </div>

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
