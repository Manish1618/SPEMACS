import React, { useState, useEffect } from 'react';
import { AlertTriangle, Zap, Activity } from 'lucide-react';
import type { HighlightAction } from '../../types';
import { api } from '../../lib/api';
import { CrossCaseIntelligence } from '../crosscase/CrossCaseIntelligence';

interface AnalyticsPanelProps {
  activeCaseId: string;
  onTriggerVisualHighlight?: (action: HighlightAction, options?: { navigate?: boolean }) => void;
}

// The retrieval tools return { records, provenance }; reading them as bare arrays
// silently rendered nothing at all.
const records = (payload: any): any[] =>
  Array.isArray(payload) ? payload : payload?.records || [];

export const AnalyticsPanel: React.FC<AnalyticsPanelProps> = ({
  activeCaseId,
  onTriggerVisualHighlight,
}) => {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [anomData, analData] = await Promise.all([
          api.getAnomalies(),
          api.getGraphAnalytics(activeCaseId)
        ]);
        setAnomalies(records(anomData));
        setAnalytics(analData);
      } catch (e) {
        console.error(e);
      }
    };
    fetchData();
  }, [activeCaseId]);

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-red-600 flex items-center justify-center shadow-lg">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Cross-Case Intelligence &amp; Automated Anomaly Detection</span>
            </h3>
            <p className="text-[11px] text-gray-400">Every detection states its basis, its confidence and what could make it wrong</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Section 1: Detected Anomalies */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              Spatial &amp; Temporal Anomalies ({anomalies.length})
            </h4>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {anomalies.map((anom, idx) => (
              <div key={idx} className="p-4 bg-amber-950/20 border border-amber-500/40 rounded-xl space-y-2.5">
                <div className="flex items-start justify-between gap-3">
                  <span className="font-bold text-amber-400 text-xs">
                    ⚡ {(anom.anomaly_type || '').replace(/_/g, ' ')}
                  </span>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {(anom.labels || []).map((label: string) => (
                      <span
                        key={label}
                        className="text-[9px] bg-dark-900 border border-amber-500/30 text-amber-200 px-1.5 py-0.5 rounded font-mono"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* What was measured against what, rather than a bare verdict */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                  <div className="p-2 bg-dark-900 rounded border border-gray-700">
                    <div className="text-[9px] uppercase font-bold text-gray-400">Observed</div>
                    <div className="text-gray-200 mt-0.5">{anom.observed}</div>
                  </div>
                  <div className="p-2 bg-dark-900 rounded border border-gray-700">
                    <div className="text-[9px] uppercase font-bold text-gray-400">Baseline</div>
                    <div className="text-gray-200 mt-0.5">{anom.baseline}</div>
                  </div>
                  <div className="p-2 bg-dark-900 rounded border border-amber-500/30">
                    <div className="text-[9px] uppercase font-bold text-amber-400">Deviation</div>
                    <div className="text-amber-200 mt-0.5">{anom.deviation}</div>
                  </div>
                </div>

                {(anom.alternative_explanations || []).length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase font-bold text-gray-400 mb-1">
                      Innocent explanations that fit the same data
                    </div>
                    <ul className="space-y-0.5">
                      {(anom.alternative_explanations || []).map((alt: string, i: number) => (
                        <li key={i} className="flex gap-2 text-[11px] text-gray-300">
                          <span className="text-gray-500 flex-shrink-0">·</span>
                          <span>{alt}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between gap-3 text-[10px]">
                  <div className="flex flex-wrap gap-1">
                    {(anom.evidence_ids || []).map((eid: string) => (
                      <span
                        key={eid}
                        className="font-mono bg-dark-900 border border-gray-700 text-indigo-300 px-1.5 py-0.5 rounded"
                      >
                        {eid}
                      </span>
                    ))}
                  </div>
                  <span className="text-gray-400 italic text-right">{anom.significance}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 2: Cross-Case Intelligence Engine */}
        <div className="min-h-[32rem]">
          <CrossCaseIntelligence
            activeCaseId={activeCaseId}
            onTriggerVisualHighlight={onTriggerVisualHighlight}
          />
        </div>

        {/* Section 3: Graph Metrics */}
        {analytics && (
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                Structural Graph Metrics
              </h4>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 bg-dark-800 rounded-xl border border-gray-800">
                <div className="text-[10px] text-gray-400 font-bold uppercase">Identified Hub Nodes (Degree)</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {(analytics.hubs || []).map((h: string) => (
                    <span key={h} className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded font-mono">
                      {h}
                    </span>
                  ))}
                </div>
              </div>

              <div className="p-3.5 bg-dark-800 rounded-xl border border-gray-800">
                <div className="text-[10px] text-gray-400 font-bold uppercase">Identified Structural Bridges (Betweenness)</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {(analytics.bridges || []).map((b: string) => (
                    <span key={b} className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono">
                      {b}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
