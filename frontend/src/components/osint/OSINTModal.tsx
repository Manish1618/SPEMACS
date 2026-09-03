import React, { useState, useEffect } from 'react';
import { Globe, AlertTriangle, ExternalLink, X } from 'lucide-react';
import type { GraphNode, OSINTRecord } from '../../types';
import { api } from '../../lib/api';

interface OSINTModalProps {
  node: GraphNode | null;
  activeCaseId: string;
  onClose: () => void;
}

export const OSINTModal: React.FC<OSINTModalProps> = ({ node, activeCaseId, onClose }) => {
  const [records, setRecords] = useState<OSINTRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!node) return;
    const fetchOSINT = async () => {
      setIsLoading(true);
      try {
        const data = await api.expandOSINT(activeCaseId, node.id, node.label, node.entity_type);
        setRecords(data);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchOSINT();
  }, [node, activeCaseId]);

  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-dark-900 border border-gray-700 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center">
              <Globe className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>Controlled OSINT Enrichment</span>
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono border border-amber-500/30">
                  Public Sources Only
                </span>
              </h3>
              <p className="text-[11px] text-gray-400">Entity: <span className="text-gray-200 font-semibold">{node.label}</span> ({node.entity_type})</p>
            </div>
          </div>

          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10 space-y-3">
              <Globe className="w-6 h-6 text-indigo-400 animate-spin" />
              <div className="text-xs text-gray-400">Querying authorized public registries & entity indices...</div>
            </div>
          ) : (
            <>
              {records.map((rec, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border ${
                    rec.is_potential_match
                      ? 'bg-amber-950/20 border-amber-500/40 border-dashed'
                      : 'bg-dark-800 border-gray-700'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-xs font-bold text-gray-200">{rec.source_name}</div>
                      <a
                        href={rec.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-indigo-400 hover:underline flex items-center space-x-1 mt-0.5"
                      >
                        <span className="truncate max-w-sm">{rec.source_url}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    </div>

                    <div className="text-right">
                      <div className="text-[10px] font-mono text-gray-400">
                        Reliability: <span className="text-emerald-400 font-bold">{Math.round(rec.reliability_score * 100)}%</span>
                      </div>
                      <div className="text-[10px] font-mono text-gray-400">
                        Confidence: <span className="text-indigo-400 font-bold">{Math.round(rec.confidence * 100)}%</span>
                      </div>
                    </div>
                  </div>

                  {rec.verification_warning && (
                    <div className="mt-2.5 flex items-center space-x-1.5 text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1.5 rounded-md border border-amber-500/20 font-semibold">
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      <span>{rec.verification_warning}</span>
                    </div>
                  )}

                  <div className="mt-3 text-xs text-gray-300 leading-relaxed bg-dark-900/60 p-3 rounded-lg border border-gray-800">
                    {rec.extracted_claims}
                  </div>

                  <div className="mt-2 text-[10px] text-gray-500 font-mono">
                    Evidence Tag: {rec.evidence_id} • Retrieved: {new Date(rec.retrieval_timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer Note */}
        <div className="p-3 border-t border-gray-800 bg-dark-800/60 text-[11px] text-gray-400 flex items-center justify-between">
          <span>⚠️ OSINT claims must be verified with primary evidence before legal submission.</span>
          <button
            onClick={onClose}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-4 py-1.5 rounded-lg font-semibold"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
