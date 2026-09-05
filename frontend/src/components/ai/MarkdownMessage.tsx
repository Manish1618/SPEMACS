import React from 'react';

/**
 * Minimal markdown renderer for investigator answers.
 *
 * The planner has always emitted markdown (headings, bullets, `[EVID-...]`
 * citation ticks, bold entity names) but the chat printed it raw, so a full
 * brief arrived as a wall of asterisks. This renders the subset the planner
 * actually produces - headings, bullets, numbered lists, bold, italic and
 * inline code - with no runtime dependency and no dangerouslySetInnerHTML.
 */

const INLINE_PATTERN = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;

const renderInline = (text: string, keyPrefix: string): React.ReactNode[] =>
  text.split(INLINE_PATTERN).filter(Boolean).map((token, i) => {
    const key = `${keyPrefix}-${i}`;
    if (token.startsWith('**') && token.endsWith('**')) {
      return <strong key={key} className="font-bold text-white">{token.slice(2, -2)}</strong>;
    }
    if (token.startsWith('`') && token.endsWith('`')) {
      return (
        <code
          key={key}
          className="px-1 py-0.5 rounded bg-dark-900 border border-indigo-500/30 text-indigo-300 font-mono text-[10px]"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    if (token.startsWith('*') && token.endsWith('*') && token.length > 2) {
      return <em key={key} className="italic text-gray-400">{token.slice(1, -1)}</em>;
    }
    return <span key={key}>{token}</span>;
  });

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'bullets'; items: string[] }
  | { type: 'ordered'; items: string[] }
  | { type: 'paragraph'; text: string };

const parseBlocks = (source: string): Block[] => {
  const blocks: Block[] = [];
  const lines = source.split('\n');
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: 'paragraph', text: paragraph.join(' ') });
      paragraph = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      continue;
    }

    const bullet = /^[-•*]\s+(.*)$/.exec(trimmed);
    if (bullet) {
      flushParagraph();
      const last = blocks[blocks.length - 1];
      if (last && last.type === 'bullets') last.items.push(bullet[1]);
      else blocks.push({ type: 'bullets', items: [bullet[1]] });
      continue;
    }

    const ordered = /^(\d+)[.)]\s+(.*)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      const last = blocks[blocks.length - 1];
      if (last && last.type === 'ordered') last.items.push(ordered[2]);
      else blocks.push({ type: 'ordered', items: [ordered[2]] });
      continue;
    }

    paragraph.push(trimmed);
  }
  flushParagraph();
  return blocks;
};

const HEADING_CLASS: Record<number, string> = {
  1: 'text-sm font-bold text-white mt-1 mb-2 pb-1.5 border-b border-gray-700/70',
  2: 'text-[12px] font-bold text-indigo-300 uppercase tracking-wide mt-3 mb-1.5',
  3: 'text-[11px] font-bold text-gray-200 mt-2 mb-1',
  4: 'text-[11px] font-semibold text-gray-300 mt-2 mb-1',
};

export const MarkdownMessage: React.FC<{ content: string; className?: string }> = ({
  content,
  className = '',
}) => {
  const blocks = React.useMemo(() => parseBlocks(content || ''), [content]);

  return (
    <div className={`text-xs leading-relaxed text-gray-200 space-y-1 ${className}`}>
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          return (
            <div key={idx} className={HEADING_CLASS[block.level] || HEADING_CLASS[4]}>
              {renderInline(block.text, `h-${idx}`)}
            </div>
          );
        }
        if (block.type === 'bullets') {
          return (
            <ul key={idx} className="space-y-1 my-1.5">
              {block.items.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-indigo-400 flex-shrink-0 leading-relaxed">•</span>
                  <span className="flex-1">{renderInline(item, `b-${idx}-${i}`)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ordered') {
          return (
            <ol key={idx} className="space-y-1 my-1.5">
              {block.items.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-indigo-400 font-mono flex-shrink-0">{i + 1}.</span>
                  <span className="flex-1">{renderInline(item, `o-${idx}-${i}`)}</span>
                </li>
              ))}
            </ol>
          );
        }
        return (
          <p key={idx} className="my-1">
            {renderInline(block.text, `p-${idx}`)}
          </p>
        );
      })}
    </div>
  );
};
