import React, { useState, useEffect } from 'react';
import { AlertTriangle, GitMerge, Zap, Activity } from 'lucide-react';
import { api } from '../../lib/api';

interface AnalyticsPanelProps {
  activeCaseId: string;
}

export const AnalyticsPanel: React.FC<AnalyticsPanelProps> = ({ activeCaseId }) => {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [crossCases, setCrossCases] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [anomData, crossData, analData] = await Promise.all([
          api.getAnomalies(),
          api.getCrossCase(),
          api.getGraphAnalytics(activeCaseId)
        ]);
        setAnomalies(anomData);
        setCrossCases(crossData);
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
              <span>Cross-Case Intelligence & Automated Anomaly Detection</span>
            </h3>
            <p className="text-[11px] text-gray-400">Heuristic rule explanation without automated accusation</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Section 1: Detected Anomalies */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              High-Confidence Spatial/Temporal Anomalies ({anomalies.length})
            </h4>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {anomalies.map((anom, idx) => (
              <div key={idx} className="p-4 bg-amber-950/20 border border-amber-500/40 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-amber-400 flex items-center space-x-1.5">
                    <span>⚡ {anom.anomaly_type.replace('_', ' ')}</span>
                  </span>
                  <span className="text-[10px] bg-amber-500/20 text-amber-300 font-mono px-2 py-0.5 rounded border border-amber-500/30">
                    Implied Speed: {anom.implied_speed_kmh} km/h
                  </span>
                </div>

                <div className="text-xs text-gray-200 leading-relaxed">
                  {anom.description}
                </div>

                <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between text-[11px] text-gray-400 font-mono">
                  <span>Dist: {anom.distance_km} km in {anom.time_span_hours} hrs</span>
                  <span className="text-amber-300">Requires Tower Handover Verification</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 2: Cross-Case Overlaps */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <GitMerge className="w-4 h-4 text-indigo-400" />
            <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              Cross-Case Shared Entities ({crossCases.length})
            </h4>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {crossCases.map((cc, idx) => (
              <div key={idx} className="p-4 bg-dark-800 border border-indigo-500/40 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-white text-sm">{cc.label}</span>
                  <div className="flex space-x-1">
                    {cc.cases.map((c: string) => (
                      <span key={c} className="text-[9px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono border border-indigo-500/30">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="text-xs text-gray-300 leading-relaxed">
                  {cc.insight}
                </div>
              </div>
            ))}
          </div>
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
