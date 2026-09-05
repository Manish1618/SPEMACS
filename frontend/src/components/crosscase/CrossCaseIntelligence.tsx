import React, { useEffect, useMemo, useState } from 'react';
import {
  GitMerge,
  ShieldCheck,
  ShieldAlert,
  Lock,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  Info,
  Route,
  AlertTriangle,
  Filter,
} from 'lucide-react';
import type { CrossCaseLink, CrossCaseReport, HighlightAction } from '../../types';
import { api } from '../../lib/api';

/**
 * Cross-Case Intelligence Engine.
 *
 * Shows where this investigation touches others the user is authorised to read,
 * and why each touch was detected. Two things this panel deliberately never does:
 * rank cases by "suspicion", and present a link as a conclusion. Confidence here
 * is confidence that the link exists in the records; the interpretation line on
 * every card says so, and the weakest signals carry the loudest caveats.
 */

interface Props {
  activeCaseId: string;
  onTriggerVisualHighlight?: (action: HighlightAction, options?: { navigate?: boolean }) => void;
}

const BAND_STYLE: Record<string, { chip: string; bar: string; label: string }> = {
  HIGH: {
    chip: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    bar: 'bg-emerald-500',
    label: 'High',
  },
  MODERATE: {
    chip: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
    bar: 'bg-amber-500',
    label: 'Moderate',
  },
  LOW: {
    chip: 'bg-gray-500/15 text-gray-300 border-gray-500/40',
    bar: 'bg-gray-500',
    label: 'Low',
  },
};

const BASIS_ICON: Record<string, React.ReactNode> = {
  CROSS_CASE_RELATIONSHIP: <GitMerge className="w-3.5 h-3.5" />,
  SHARED_ENTITY: <ShieldCheck className="w-3.5 h-3.5" />,
  SHARED_ARTIFACT: <ShieldCheck className="w-3.5 h-3.5" />,
  IDENTIFIER_MATCH: <ShieldCheck className="w-3.5 h-3.5" />,
  ALIAS_MATCH: <AlertTriangle className="w-3.5 h-3.5" />,
  MULTI_HOP_PATH: <Route className="w-3.5 h-3.5" />,
  SHARED_LOCATION: <AlertTriangle className="w-3.5 h-3.5" />,
  TEMPORAL_PATTERN: <AlertTriangle className="w-3.5 h-3.5" />,
};

const LinkCard: React.FC<{
  link: CrossCaseLink;
  onOpen?: (link: CrossCaseLink) => void;
}> = ({ link, onOpen }) => {
  const [open, setOpen] = useState(false);
  const band = BAND_STYLE[link.confidence_band] || BAND_STYLE.LOW;

  return (
    <div className="rounded-xl border border-gray-700 bg-dark-800 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full text-left p-3.5 hover:bg-gray-800/40 transition-colors"
      >
        <div className="flex items-start gap-2.5">
          {open ? (
            <ChevronDown className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
          )}

          <div className="flex-1 min-w-0 space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded border ${band.chip}`}
              >
                {BASIS_ICON[link.basis]}
                {link.basis_label}
              </span>
              <span className="text-[10px] font-mono text-gray-400">
                {link.case_b.case_id}
              </span>
              {link.hops > 1 && (
                <span className="text-[9px] font-mono text-indigo-300 bg-indigo-500/15 border border-indigo-500/30 px-1.5 py-0.5 rounded">
                  {link.hops} hops
                </span>
              )}
              {link.requires_human_verification && (
                <span className="text-[9px] font-bold text-amber-300 bg-amber-500/15 border border-amber-500/40 px-1.5 py-0.5 rounded">
                  NEEDS VERIFICATION
                </span>
              )}
            </div>

            <div className="text-xs text-gray-200 leading-relaxed">{link.summary}</div>

            <div className="flex items-center gap-2">
              <div className="h-1 w-24 bg-dark-900 rounded overflow-hidden">
                <div
                  className={`h-full ${band.bar}`}
                  style={{ width: `${Math.round(link.confidence * 100)}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-gray-400">
                {band.label} · {link.confidence.toFixed(2)} that the link exists in the records
              </span>
            </div>
          </div>
        </div>
      </button>

      {open && (
        <div className="px-3.5 pb-3.5 space-y-3 border-t border-gray-700/60 pt-3">
          {/* Why it was detected */}
          <div>
            <div className="text-[10px] uppercase font-bold text-indigo-300 mb-1.5">
              Basis for this link
            </div>
            <ul className="space-y-1">
              {link.explanation.map((step, i) => (
                <li key={i} className="flex gap-2 text-[11px] text-gray-300">
                  <span className="text-indigo-400 font-mono flex-shrink-0">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Path, for indirect links */}
          {link.path.length > 0 && (
            <div>
              <div className="text-[10px] uppercase font-bold text-indigo-300 mb-1.5">
                Recorded path
              </div>
              <div className="flex flex-wrap items-center gap-1 text-[10px] font-mono">
                <span className="bg-dark-900 border border-gray-700 px-1.5 py-0.5 rounded text-gray-200">
                  {link.path[0].from_label}
                </span>
                {link.path.map((step, i) => (
                  <React.Fragment key={i}>
                    <span className="text-amber-300">—{step.rel_type}→</span>
                    <span className="bg-dark-900 border border-gray-700 px-1.5 py-0.5 rounded text-gray-200">
                      {step.to_label}
                    </span>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Supporting evidence */}
          {link.supporting_evidence.length > 0 && (
            <div>
              <div className="text-[10px] uppercase font-bold text-emerald-400 mb-1.5">
                Supporting evidence ({link.supporting_evidence.length})
              </div>
              <div className="space-y-1">
                {link.supporting_evidence.map(item => (
                  <div
                    key={item.evidence_id}
                    className="flex items-center justify-between gap-2 text-[10.5px] bg-dark-900 border border-gray-700 rounded px-2 py-1"
                  >
                    <span className="font-mono text-indigo-300 flex-shrink-0">
                      {item.evidence_id}
                    </span>
                    <span className="text-gray-300 flex-1 truncate">{item.title}</span>
                    <span
                      className={`font-mono flex-shrink-0 ${
                        item.integrity_status === 'VERIFIED' ? 'text-emerald-400' : 'text-amber-400'
                      }`}
                    >
                      {item.integrity_status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Contradicting evidence */}
          {link.contradicting_evidence.length > 0 && (
            <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-lg">
              <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-red-300 mb-1.5">
                <ShieldAlert className="w-3.5 h-3.5" />
                Contradicting evidence
              </div>
              {link.contradicting_evidence.map((problem, i) => (
                <div key={i} className="text-[11px] space-y-0.5">
                  <div className="text-red-300 font-semibold">{problem.source}</div>
                  <div className="text-gray-300">{problem.discrepancy}</div>
                </div>
              ))}
            </div>
          )}

          {/* Uncertainty */}
          <div className="p-2.5 bg-amber-950/20 border border-amber-500/30 rounded-lg">
            <div className="text-[10px] uppercase font-bold text-amber-300 mb-1.5">
              What could make this wrong
            </div>
            <ul className="space-y-1">
              {link.uncertainty.map((u, i) => (
                <li key={i} className="flex gap-2 text-[11px] text-gray-300">
                  <span className="text-amber-400 flex-shrink-0">·</span>
                  <span>{u}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* The non-inference line, on every single card */}
          <div className="flex gap-2 text-[10.5px] text-gray-400 italic border-l-2 border-gray-700 pl-2">
            <Info className="w-3.5 h-3.5 flex-shrink-0 text-gray-500 mt-0.5" />
            <span>{link.interpretation}</span>
          </div>

          {onOpen && (link.view_sync.node_ids.length > 0 || link.view_sync.event_ids.length > 0) && (
            <button
              onClick={() => onOpen(link)}
              className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-1.5 px-3 rounded-lg text-xs font-semibold shadow transition-colors"
            >
              <span>Open in Graph, Map &amp; Timeline</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export const CrossCaseIntelligence: React.FC<Props> = ({
  activeCaseId,
  onTriggerVisualHighlight,
}) => {
  const [report, setReport] = useState<CrossCaseReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minBand, setMinBand] = useState<'ALL' | 'HIGH' | 'MODERATE'>('ALL');
  const [basisFilter, setBasisFilter] = useState<string>('ALL');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getCrossCaseAnalysis(activeCaseId);
        if (!cancelled) setReport(data);
      } catch (e) {
        console.error(e);
        if (!cancelled) setError('Could not reach the cross-case engine. Is the backend running?');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [activeCaseId]);

  // Derived from `report` rather than from a fresh array each render, so the
  // filter does not recompute on every unrelated state change.
  const visible = useMemo(() => {
    const floor = minBand === 'HIGH' ? 0.8 : minBand === 'MODERATE' ? 0.5 : 0;
    return (report?.links || []).filter(
      link =>
        link.confidence >= floor && (basisFilter === 'ALL' || link.basis === basisFilter)
    );
  }, [report, minBand, basisFilter]);

  const links = report?.links || [];

  const handleOpen = (link: CrossCaseLink) => {
    onTriggerVisualHighlight?.(
      {
        target_type: 'multi_view',
        node_ids: link.view_sync.node_ids,
        event_ids: link.view_sync.event_ids,
        coordinates: link.view_sync.coordinates,
        description: `Cross-case link (${link.basis_label}): ${link.summary}`,
      },
      { navigate: true }
    );
  };

  const auth = report?.authorisation;
  const authNote = typeof auth === 'string' ? auth : auth?.note;

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-cyan-500 flex items-center justify-center shadow-lg">
            <GitMerge className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Cross-Case Intelligence Engine</h3>
            <p className="text-[11px] text-gray-400">
              Detected relationships to other investigations, with the basis for each
            </p>
          </div>
        </div>

        {report?.summary && (
          <div className="flex items-center gap-2 text-[10px] font-mono">
            <span className="px-2 py-1 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
              {report.summary.by_band.HIGH} high
            </span>
            <span className="px-2 py-1 rounded border border-amber-500/40 bg-amber-500/10 text-amber-300">
              {report.summary.by_band.MODERATE} moderate
            </span>
            <span className="px-2 py-1 rounded border border-gray-600 bg-gray-500/10 text-gray-300">
              {report.summary.by_band.LOW} low
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {loading && (
          <div className="text-xs text-gray-400">Comparing this case against your authorised scope…</div>
        )}

        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-300">
            {error}
          </div>
        )}

        {/* The rule that governs how everything below may be read */}
        {report && (
          <div className="p-3.5 bg-indigo-950/30 border border-indigo-500/40 rounded-xl flex gap-2.5">
            <Info className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1.5 text-[11px] leading-relaxed">
              <div className="text-gray-200">{report.caveat}</div>
              {report.confidence_meaning && (
                <div className="text-gray-400">{report.confidence_meaning}</div>
              )}
            </div>
          </div>
        )}

        {/* Authorisation boundary */}
        {authNote && (
          <div className="p-3 bg-dark-800 border border-gray-700 rounded-xl flex gap-2.5">
            <Lock className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
            <div className="text-[11px] text-gray-300 leading-relaxed">
              <span className="font-bold text-cyan-300">Search scope: </span>
              {authNote}
              {typeof auth !== 'string' && auth && (
                <span className="text-gray-400">
                  {' '}
                  Requested by {auth.username} ({auth.role}).
                </span>
              )}
            </div>
          </div>
        )}

        {/* Related cases */}
        {report?.related_cases && report.related_cases.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              Related investigations ({report.related_cases.length})
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {report.related_cases.map(rc => (
                <div key={rc.case_id} className="p-3.5 bg-dark-800 border border-gray-700 rounded-xl space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-bold text-white">{rc.title}</div>
                      <div className="text-[10px] font-mono text-gray-400">
                        {rc.case_id} · {rc.status}
                      </div>
                    </div>
                    <span className="text-[10px] font-mono bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded flex-shrink-0">
                      {rc.link_count} links
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {rc.bases.map(b => (
                      <span
                        key={b}
                        className="text-[9px] font-mono bg-dark-900 border border-gray-700 text-gray-300 px-1.5 py-0.5 rounded"
                      >
                        {b.replace(/_/g, ' ').toLowerCase()}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        {links.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-gray-500" />
            <select
              value={minBand}
              onChange={e => setMinBand(e.target.value as typeof minBand)}
              aria-label="Minimum confidence band"
              className="bg-dark-800 border border-gray-700 text-[11px] text-gray-300 rounded px-2 py-1 focus:outline-none"
            >
              <option value="ALL">All confidence bands</option>
              <option value="MODERATE">Moderate and above</option>
              <option value="HIGH">High only</option>
            </select>
            <select
              value={basisFilter}
              onChange={e => setBasisFilter(e.target.value)}
              aria-label="Detection basis"
              className="bg-dark-800 border border-gray-700 text-[11px] text-gray-300 rounded px-2 py-1 focus:outline-none"
            >
              <option value="ALL">All detection bases</option>
              {Object.entries(report?.summary?.by_basis || {}).map(([basis, count]) => (
                <option key={basis} value={basis}>
                  {basis.replace(/_/g, ' ').toLowerCase()} ({count})
                </option>
              ))}
            </select>
            <span className="text-[10px] text-gray-500 font-mono">
              showing {visible.length} of {links.length}
            </span>
          </div>
        )}

        {/* Links */}
        <div className="space-y-2.5">
          {visible.map(link => (
            <LinkCard key={link.link_id} link={link} onOpen={handleOpen} />
          ))}
        </div>

        {/* An empty result is a statement about the search, not about the world */}
        {!loading && report?.authorised && links.length === 0 && (
          <div className="p-4 bg-dark-800 border border-gray-700 rounded-xl text-xs text-gray-300 leading-relaxed">
            No relationship was detected between this investigation and any other case in your
            authorised scope.
            <span className="text-gray-400">
              {' '}
              That means nothing was found in the records searched. It is not a finding that no
              relationship exists.
            </span>
          </div>
        )}

        {!loading && report && !report.authorised && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-300">
            {typeof report.authorisation === 'string'
              ? report.authorisation
              : 'You are not authorised to run cross-case analysis on this case.'}
          </div>
        )}
      </div>
    </div>
  );
};
