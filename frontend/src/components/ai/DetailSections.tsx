import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Layers, Search } from 'lucide-react';
import type { DetailSection } from '../../types';

/**
 * Renders the full record set the investigator asked for, inline in the chat.
 *
 * Each section arrives typed (stats / keyvalue / table / list / group) so the
 * backend decides what a section contains and this component only decides how
 * it looks. Sections start collapsed apart from the first, and tables carry a
 * row filter so a 60-row chronology stays usable inside a chat bubble.
 */

const TONE_CLASS: Record<string, string> = {
  good: 'border-emerald-500/40 text-emerald-300',
  bad: 'border-red-500/50 text-red-300',
};

const StatGrid: React.FC<{ section: DetailSection }> = ({ section }) => (
  <div className="space-y-3">
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {(section.stats || []).map((stat, i) => (
        <div
          key={i}
          className={`p-2 bg-dark-900 rounded-lg border text-center ${
            TONE_CLASS[stat.tone || ''] || 'border-gray-700 text-white'
          }`}
        >
          <div className="text-[9px] uppercase tracking-wide text-gray-400">{stat.label}</div>
          <div className="text-sm font-bold font-mono mt-0.5">{stat.value}</div>
        </div>
      ))}
    </div>
    {section.pairs && <KeyValueList section={section} />}
  </div>
);

const KeyValueList: React.FC<{ section: DetailSection }> = ({ section }) => (
  <div className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
    {(section.pairs || []).map((pair, i) => (
      <div key={i} className="grid grid-cols-3 gap-2 px-2.5 py-1.5 text-[11px] odd:bg-dark-900/60">
        <div className="text-gray-400 font-semibold col-span-1">{pair[0]}</div>
        <div className="text-gray-200 col-span-2 break-words">{pair[1]}</div>
      </div>
    ))}
  </div>
);

const TableView: React.FC<{ section: DetailSection }> = ({ section }) => {
  const [filter, setFilter] = useState('');
  const rows = section.rows || [];
  const needle = filter.trim().toLowerCase();
  const visible = needle
    ? rows.filter((row) => row.some((cell) => String(cell).toLowerCase().includes(needle)))
    : rows;
  const hidden = (section.total_rows || rows.length) - rows.length;

  return (
    <div className="space-y-2">
      {rows.length > 8 && (
        <div className="flex items-center gap-1.5 bg-dark-900 border border-gray-700 rounded px-2 py-1">
          <Search className="w-3 h-3 text-gray-500 flex-shrink-0" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={`Filter ${rows.length} rows…`}
            className="bg-transparent text-[11px] text-gray-200 outline-none w-full"
          />
          {needle && (
            <span className="text-[10px] text-gray-500 font-mono flex-shrink-0">
              {visible.length}/{rows.length}
            </span>
          )}
        </div>
      )}

      <div className="overflow-x-auto border border-gray-800 rounded-lg">
        <table className="w-full text-[10.5px] border-collapse">
          <thead>
            <tr className="bg-dark-900">
              {(section.columns || []).map((col, i) => (
                <th
                  key={i}
                  className="text-left px-2 py-1.5 font-bold text-gray-400 uppercase tracking-wide whitespace-nowrap border-b border-gray-800"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, rIdx) => (
              <tr key={rIdx} className="odd:bg-dark-900/50 align-top">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-2 py-1.5 text-gray-200 border-b border-gray-800/60">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td
                  colSpan={(section.columns || []).length || 1}
                  className="px-2 py-3 text-center text-gray-500"
                >
                  No rows match “{filter}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {hidden > 0 && (
        <div className="text-[10px] text-amber-400/80">
          Showing the first {rows.length} of {section.total_rows} rows. The remaining {hidden} are in
          the case record store — narrow the question to bring them into the answer.
        </div>
      )}
    </div>
  );
};

const ListView: React.FC<{ section: DetailSection }> = ({ section }) => (
  <ul className="space-y-1.5">
    {(section.items || []).map((item, i) => {
      const isGap = item.startsWith('GAP · ');
      const isAction = item.startsWith('ACTION · ');
      const body = isGap || isAction ? item.split('· ').slice(1).join('· ') : item;
      return (
        <li key={i} className="flex gap-2 text-[11px]">
          <span
            className={`flex-shrink-0 font-bold font-mono text-[9px] px-1.5 py-0.5 rounded border h-fit ${
              isGap
                ? 'text-amber-300 border-amber-500/40 bg-amber-500/10'
                : isAction
                  ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
                  : 'text-gray-400 border-gray-700'
            }`}
          >
            {isGap ? 'GAP' : isAction ? 'ACTION' : '•'}
          </span>
          <span className="text-gray-200 flex-1">{body}</span>
        </li>
      );
    })}
  </ul>
);

const SectionBody: React.FC<{ section: DetailSection; depth: number }> = ({ section, depth }) => {
  switch (section.kind) {
    case 'stats':
      return <StatGrid section={section} />;
    case 'keyvalue':
      return <KeyValueList section={section} />;
    case 'table':
      return <TableView section={section} />;
    case 'list':
      return <ListView section={section} />;
    case 'group':
      return (
        <div className="space-y-2">
          {(section.children || []).map((child) => (
            <SectionCard key={child.section_id} section={child} depth={depth + 1} />
          ))}
        </div>
      );
    default:
      return null;
  }
};

const SectionCard: React.FC<{ section: DetailSection; depth?: number; defaultOpen?: boolean }> = ({
  section,
  depth = 0,
  defaultOpen = false,
}) => {
  const [open, setOpen] = useState(defaultOpen);
  const count =
    section.total_rows ?? section.items?.length ?? section.children?.length ?? section.pairs?.length;

  return (
    <div
      className={`rounded-lg border overflow-hidden ${
        depth === 0 ? 'border-gray-700 bg-dark-900/70' : 'border-gray-800 bg-dark-900/40'
      }`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-2.5 py-2 text-left hover:bg-gray-800/40 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
        )}
        <span className={`font-bold ${depth === 0 ? 'text-[11.5px] text-white' : 'text-[11px] text-gray-200'}`}>
          {section.title}
        </span>
        {count !== undefined && (
          <span className="text-[9px] font-mono text-gray-400 bg-dark-800 border border-gray-700 px-1.5 py-0.5 rounded flex-shrink-0">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div className="px-2.5 pb-2.5 space-y-2">
          {section.summary && (
            <div className="text-[10.5px] text-gray-400 italic">{section.summary}</div>
          )}
          <SectionBody section={section} depth={depth} />
        </div>
      )}
    </div>
  );
};

export const DetailSections: React.FC<{
  sections: DetailSection[];
  stats?: Record<string, number> | null;
}> = ({ sections, stats }) => {
  const [allOpen, setAllOpen] = useState(false);

  if (!sections?.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-700/60 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-bold text-amber-300 uppercase tracking-wider">
          <Layers className="w-3.5 h-3.5" />
          <span>Full record set ({sections.length} sections)</span>
        </div>
        <button
          onClick={() => setAllOpen((v) => !v)}
          className="text-[10px] text-indigo-400 hover:text-indigo-300 hover:underline"
        >
          {allOpen ? 'Collapse all' : 'Expand all'}
        </button>
      </div>

      {stats && (
        <div className="text-[10px] text-gray-400 font-mono">
          {Object.entries(stats)
            .map(([key, value]) => `${value} ${key.replace(/_/g, ' ')}`)
            .join(' · ')}
        </div>
      )}

      <div className="space-y-2">
        {sections.map((section, idx) => (
          // Remounting on the expand-all toggle is what applies the new default
          // open state to every card, including nested ones.
          <SectionCard
            key={`${section.section_id}-${allOpen}`}
            section={section}
            defaultOpen={allOpen || idx === 0}
          />
        ))}
      </div>
    </div>
  );
};
