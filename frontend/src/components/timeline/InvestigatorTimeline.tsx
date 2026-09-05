import React, { useState, useEffect, useRef } from 'react';
import type { TimelineEvent } from '../../types';
import { Play, Pause, RotateCcw, Clock, Phone, DollarSign, Camera, Users, HelpCircle } from 'lucide-react';

interface InvestigatorTimelineProps {
  events: TimelineEvent[];
  selectedEventId: string | null;
  onSelectEvent: (event: TimelineEvent | null) => void;
  activeTimeFilter: string | null;
  onTimeFilterChange: (time: string | null) => void;
  onAskCopilotAboutEvent?: (event: TimelineEvent) => void;
}

export const InvestigatorTimeline: React.FC<InvestigatorTimelineProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  onTimeFilterChange,
  onAskCopilotAboutEvent
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Playback timer loop
  useEffect(() => {
    let interval: any = null;
    if (isPlaying && events.length > 0) {
      interval = setInterval(() => {
        setCurrentIndex((prev) => {
          const next = prev + 1;
          if (next >= events.length) {
            setIsPlaying(false);
            return prev;
          }
          const nextEvt = events[next];
          setTimeout(() => {
            onSelectEvent(nextEvt);
            onTimeFilterChange(nextEvt.start_time);
          }, 0);
          return next;
        });
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying, events]);

  const getEventIcon = (type: string) => {
    if (type.includes('CALL') || type.includes('CDR')) return <Phone className="w-3 h-3 text-blue-400" />;
    if (type.includes('TRANSACTION') || type.includes('BANK')) return <DollarSign className="w-3 h-3 text-emerald-400" />;
    if (type.includes('TOLL') || type.includes('CCTV')) return <Camera className="w-3 h-3 text-amber-400" />;
    return <Users className="w-3 h-3 text-red-400" />;
  };

  return (
    <div className="w-full bg-dark-900 border-t border-gray-800 p-3 flex flex-col space-y-2">
      {/* Header & Playback Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Clock className="w-4 h-4 text-indigo-400" />
          <span className="text-xs font-bold text-gray-200">Chronological Event Timeline & Investigation Replay</span>
          <span className="text-[10px] bg-dark-800 text-gray-400 px-2 py-0.5 rounded border border-gray-700">
            {events.length} Events Logged
          </span>
        </div>

        {/* Scrubber controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setCurrentIndex(0);
              if (events.length > 0) {
                onSelectEvent(events[0]);
                onTimeFilterChange(events[0].start_time);
              }
            }}
            className="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-white"
            title="Reset Timeline to Start"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`flex items-center space-x-1 text-xs px-3 py-1 rounded-md font-semibold transition-colors shadow ${
              isPlaying
                ? 'bg-amber-600 hover:bg-amber-500 text-white animate-pulse'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isPlaying ? 'Pause Replay' : 'Investigation Replay'}</span>
          </button>
        </div>
      </div>

      {/* Horizontal Timeline Scroll Card Series */}
      <div ref={scrollContainerRef} className="flex items-center space-x-3 overflow-x-auto py-2 px-1">
        {events.map((evt, idx) => {
          const isSelected = evt.id === selectedEventId || (currentIndex === idx && isPlaying);
          return (
            <div
              key={evt.id}
              onClick={() => {
                setCurrentIndex(idx);
                onSelectEvent(evt);
                onTimeFilterChange(evt.start_time);
              }}
              className={`flex-shrink-0 w-64 p-2.5 rounded-lg border transition-all cursor-pointer ${
                isSelected
                  ? 'bg-indigo-950/60 border-indigo-500 shadow-lg shadow-indigo-500/20 ring-1 ring-indigo-500'
                  : 'bg-dark-800/80 border-gray-800 hover:border-gray-700 hover:bg-dark-800'
              }`}
            >
              <div className="flex items-center justify-between text-[10px]">
                <div className="flex items-center space-x-1.5 font-mono text-gray-400">
                  {getEventIcon(evt.event_type)}
                  <span>{new Date(evt.start_time).toLocaleDateString()} {new Date(evt.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                {evt.evidence_id && (
                  <span className="text-[9px] text-emerald-400 font-mono font-semibold bg-emerald-500/10 px-1 py-0.5 rounded border border-emerald-500/20">
                    {evt.evidence_id}
                  </span>
                )}
              </div>

              <div className="text-xs font-bold text-gray-200 mt-1 truncate">{evt.title}</div>
              <div className="text-[11px] text-gray-400 mt-0.5 line-clamp-1">{evt.summary}</div>

              <div className="flex items-center justify-between mt-1">
                {evt.location_name ? (
                  <div className="text-[10px] text-indigo-400 truncate">
                    📍 {evt.location_name}
                  </div>
                ) : <div />}

                {onAskCopilotAboutEvent && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onAskCopilotAboutEvent(evt);
                    }}
                    title="Ask AI: Why is this event important?"
                    className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center space-x-0.5"
                  >
                    <HelpCircle className="w-3 h-3" />
                    <span>Explain</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
