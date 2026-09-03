import React, { useState } from 'react';
import { GitMerge, Check, X, UserCheck } from 'lucide-react';
import { api } from '../../lib/api';

interface EntityResolutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onMerged: () => void;
}

export const EntityResolutionModal: React.FC<EntityResolutionModalProps> = ({
  isOpen,
  onClose,
  onMerged
}) => {
  const [candidates, setCandidates] = useState([
    {
      candidate_id: 'RES-01',
      primary_entity: { id: 'ENT-PER-01', name: 'Vikram Malhotra', type: 'Person', phone: '+919811022331', pan: 'ABCDE1234F', case: 'CASE-2024-8812' },
      duplicate_entity: { id: 'ENT-PER-01-ALIAS', name: 'Vicky (FIR Alias)', type: 'Person', phone: '+919811022331', pan: 'Unverified', case: 'CASE-2024-8812' },
      confidence_score: 0.94,
      match_reasons: ['Exact Phone Number Match (+919811022331)', 'Alias mention in FIR Section 4'],
      status: 'PENDING_REVIEW'
    },
    {
      candidate_id: 'RES-02',
      primary_entity: { id: 'ENT-PER-03', name: 'Rahul Sharma', type: 'Person', phone: '+919871144553', role: 'Courier', case: 'CASE-2024-8812' },
      duplicate_entity: { id: 'ENT-PER-04', name: 'Rahul Verma', type: 'Person', phone: '+919810077889', role: 'Associate', case: 'CASE-2024-8812' },
      confidence_score: 0.72,
      match_reasons: ['First Name Match (Rahul)', 'Connected to same telecom cluster'],
      status: 'NEEDS_VERIFICATION'
    }
  ]);

  const [mergingId, setMergingId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleMerge = async (cand: any) => {
    setMergingId(cand.candidate_id);
    try {
      await api.mergeEntities(cand.primary_entity.id, cand.duplicate_entity.id);
      setCandidates(prev => prev.map(c => c.candidate_id === cand.candidate_id ? { ...c, status: 'MERGED' } : c));
      onMerged();
    } catch (e) {
      console.error(e);
    } finally {
      setMergingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-dark-900 border border-gray-700 rounded-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-800 bg-dark-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center">
              <GitMerge className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>Entity Resolution & Deduplication Studio</span>
                <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono border border-indigo-500/30">
                  Provenance Tracking
                </span>
              </h3>
              <p className="text-[11px] text-gray-400">Review and resolve potential duplicate entities and alias linkages</p>
            </div>
          </div>

          <button onClick={onClose} className="text-gray-400 hover:text-white p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* List of Candidates */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {candidates.map((cand) => {
            const isMerged = cand.status === 'MERGED';

            return (
              <div key={cand.candidate_id} className="p-4 bg-dark-800 border border-gray-700 rounded-2xl space-y-3 shadow-lg">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-gray-400">{cand.candidate_id}</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-400">Match Confidence:</span>
                    <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                      cand.confidence_score >= 0.90
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                    }`}>
                      {Math.round(cand.confidence_score * 100)}%
                    </span>
                  </div>
                </div>

                {/* Side-by-Side Comparison Grid */}
                <div className="grid grid-cols-2 gap-4">
                  {/* Primary Entity */}
                  <div className="p-3 bg-dark-900 rounded-xl border border-indigo-500/40 space-y-1">
                    <div className="text-[10px] font-bold uppercase text-indigo-400">Canonical Entity (Primary)</div>
                    <div className="text-sm font-bold text-white">{cand.primary_entity.name}</div>
                    <div className="text-[11px] text-gray-400">ID: {cand.primary_entity.id}</div>
                    <div className="text-[11px] text-gray-300">Phone: {cand.primary_entity.phone}</div>
                  </div>

                  {/* Duplicate Entity */}
                  <div className="p-3 bg-dark-900 rounded-xl border border-amber-500/40 space-y-1">
                    <div className="text-[10px] font-bold uppercase text-amber-400">Candidate Match (Alias/Dup)</div>
                    <div className="text-sm font-bold text-white">{cand.duplicate_entity.name}</div>
                    <div className="text-[11px] text-gray-400">ID: {cand.duplicate_entity.id}</div>
                    <div className="text-[11px] text-gray-300">Phone: {cand.duplicate_entity.phone}</div>
                  </div>
                </div>

                {/* Match Reasons */}
                <div className="text-xs text-gray-400 space-y-1 bg-dark-900/60 p-2.5 rounded border border-gray-800">
                  <div className="text-[10px] font-bold text-gray-300 uppercase">Detection Reasons:</div>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px] text-gray-300">
                    {cand.match_reasons.map((r, rIdx) => (
                      <li key={rIdx}>{r}</li>
                    ))}
                  </ul>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-700/60">
                  {isMerged ? (
                    <span className="text-xs text-emerald-400 font-bold flex items-center space-x-1">
                      <Check className="w-4 h-4" />
                      <span>Merged & Rerouted</span>
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => handleMerge(cand)}
                        disabled={mergingId === cand.candidate_id}
                        className="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-1.5 px-3 rounded-lg transition-colors shadow"
                      >
                        <UserCheck className="w-3.5 h-3.5" />
                        <span>Confirm & Merge Entity</span>
                      </button>

                      <button
                        onClick={() => setCandidates(prev => prev.filter(c => c.candidate_id !== cand.candidate_id))}
                        className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold py-1.5 px-3 rounded-lg transition-colors"
                      >
                        Keep Separate
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
