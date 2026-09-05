import React, { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, CheckCircle, ShieldAlert, CornerDownRight, HelpCircle, Mic, MicOff, Lightbulb, Scale, ArrowRight, ListTree, Globe2, Copy, Check, Maximize2 } from 'lucide-react';
import type { AIResponse, HighlightAction } from '../../types';
import { api } from '../../lib/api';
import { MarkdownMessage } from './MarkdownMessage';
import { DetailSections } from './DetailSections';

interface UniversalAIInvestigatorProps {
  activeCaseId: string;
  onTriggerVisualHighlight: (action: HighlightAction, options?: { navigate?: boolean }) => void;
  onOpenDocumentViewer?: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  responseObj?: AIResponse;
}

export const UniversalAIInvestigator: React.FC<UniversalAIInvestigatorProps> = ({
  activeCaseId,
  onTriggerVisualHighlight,
  onOpenDocumentViewer
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: [
        "Hello Inspector. I am the **SPEMASS Universal AI Investigator**, running a **Dynamic Investigation Query Planner** over the case knowledge graph, scanned FIRs, CCTV transcripts, CDR tower telemetry, bank ledgers and authorized OSINT.",
        "",
        "Two ways to work:",
        "- Ask anything in your own words and I answer the question you asked, with citations.",
        "- Ask for **full information** - or flip the **Full Info** switch above - and the complete record set comes back in this chat: entity roster, relationship matrix, full chronology, financial trail, communications, evidence register with digests and custody, network analytics, OSINT independence, and the gaps.",
        "",
        "Name a subject and you get their individual dossier attached as well."
      ].join("\n")
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState<'chat' | 'hypotheses'>('chat');
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  // Full Info mode: every answer also carries the complete case record set.
  const [fullDetail, setFullDetail] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // A full brief is far taller than the viewport, so without this the answer
  // lands below the fold and nothing on screen moves when it arrives.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading]);

  const sampleQueries = [
    "Give me the full case brief with everything on file",
    "Tell me everything about Vikram Malhotra",
    "Show all networks and connected entities in this case",
    "Find unusual relationships that appeared after Person A met Person B and tell me whether any evidence connects them to this case.",
    "Where was Vikram on Feb 14 and is there any contradicting evidence?",
    "Show calls made by Rahul",
    "Are there any cross-case links to past operations?",
    "Has any of this evidence been modified?"
  ];

  // Fetch Hypotheses
  useEffect(() => {
    const fetchHypotheses = async () => {
      try {
        const data = await api.getHypotheses(activeCaseId);
        setHypotheses(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error(e);
      }
    };
    fetchHypotheses();
  }, [activeCaseId]);

  // Web Speech API Voice Recognition
  const toggleVoiceRecording = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    if (!isRecording) {
      setIsRecording(true);
      recognition.start();

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputQuery(transcript);
        setIsRecording(false);
        handleSend(transcript);
      };

      recognition.onerror = () => {
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };
    } else {
      setIsRecording(false);
    }
  };

  const handleSend = async (queryText?: string) => {
    const q = queryText || inputQuery;
    if (!q.trim() || isLoading) return;

    const newMessages: Message[] = [...messages, { role: 'user', content: q }];
    setMessages(newMessages);
    setInputQuery('');
    setIsLoading(true);

    try {
      const historyPayload = newMessages.map(m => ({ role: m.role, content: m.content }));
      const response: AIResponse = await api.investigate(
        activeCaseId,
        q,
        historyPayload,
        fullDetail ? 'full' : 'standard'
      );

      setMessages([...newMessages, {
        role: 'assistant',
        content: response.answer,
        responseObj: response
      }]);

      if (response.visual_actions) {
        // Apply the highlight now, but leave the investigator reading the answer.
        onTriggerVisualHighlight(response.visual_actions, { navigate: false });
      }
    } catch (err) {
      setMessages([...newMessages, {
        role: 'assistant',
        content: "Error communicating with the investigation reasoning pipeline. Please verify the backend is running."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header Banner */}
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Universal AI Investigator</span>
              <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono border border-indigo-500/30">
                Dynamic Query Planner Active
              </span>
            </h3>
            <p className="text-[11px] text-gray-400">Open-ended investigation reasoning & strict citation guardrails</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Full Info switch: attaches the complete record set to every answer */}
          <button
            onClick={() => setFullDetail(v => !v)}
            title={
              fullDetail
                ? 'Full Info is on: answers arrive with the complete case record set attached.'
                : 'Full Info is off: answers stay focused on the question asked.'
            }
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              fullDetail
                ? 'bg-amber-500/20 text-amber-200 border-amber-500/50 shadow'
                : 'bg-dark-900 text-gray-400 border-gray-700 hover:text-white'
            }`}
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span>Full Info</span>
            <span
              className={`w-7 h-3.5 rounded-full relative transition-colors ${
                fullDetail ? 'bg-amber-500' : 'bg-gray-700'
              }`}
            >
              <span
                className={`absolute top-0.5 w-2.5 h-2.5 rounded-full bg-white transition-all ${
                  fullDetail ? 'left-4' : 'left-0.5'
                }`}
              />
            </span>
          </button>

        {/* Sub-Tabs Switcher */}
        <div className="flex items-center space-x-1 bg-dark-900 p-1 rounded-lg border border-gray-700">
          <button
            onClick={() => setActiveSubTab('chat')}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
              activeSubTab === 'chat'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Investigative Chat
          </button>
          <button
            onClick={() => setActiveSubTab('hypotheses')}
            className={`flex items-center space-x-1 px-3 py-1 rounded text-xs font-semibold transition-all ${
              activeSubTab === 'hypotheses'
                ? 'bg-amber-600 text-white shadow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Lightbulb className="w-3.5 h-3.5 text-amber-300" />
            <span>Theories & Hypotheses</span>
          </button>
          </div>
        </div>
      </div>

      {activeSubTab === 'chat' ? (
        <>
          {/* Quick Prompts Bar */}
          <div className="p-2.5 bg-dark-900 border-b border-gray-800/80 flex items-center space-x-2 overflow-x-auto">
            <span className="text-[10px] uppercase font-bold text-gray-500 flex-shrink-0">
              {fullDetail ? 'Full Info mode · Sample Questions:' : 'Sample Questions:'}
            </span>
            {sampleQueries.map((sq, i) => (
              <button
                key={i}
                onClick={() => handleSend(sq)}
                className="flex-shrink-0 text-xs bg-dark-800 hover:bg-gray-800 text-gray-300 hover:text-white px-2.5 py-1 rounded-full border border-gray-700/70 transition-colors truncate max-w-xs"
              >
                {sq}
              </button>
            ))}
          </div>

          {/* Messages List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`rounded-xl p-4 text-xs leading-relaxed ${
                    msg.responseObj?.detail_sections?.length ? 'max-w-full w-full' : 'max-w-[88%]'
                  } ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-tr-none shadow-md'
                      : 'bg-dark-800 border border-gray-700/70 text-gray-200 rounded-tl-none shadow-md'
                  }`}
                >
                  {/* Dynamic Query Plan Accordion Banner */}
                  {msg.responseObj?.query_plan && msg.responseObj.query_plan.length > 0 && (
                    <div className="mb-3 p-2.5 bg-indigo-950/40 border border-indigo-500/40 rounded-lg text-xs space-y-1.5">
                      <div className="flex items-center space-x-1.5 font-bold text-indigo-300 text-[11px]">
                        <ListTree className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Dynamic Execution Plan ({msg.responseObj.query_plan.length} Steps)</span>
                      </div>
                      <div className="grid grid-cols-1 gap-1 pt-1 font-mono text-[10px]">
                        {msg.responseObj.query_plan.map((step, sIdx) => (
                          <div key={sIdx} className="flex items-center space-x-2 text-gray-300">
                            <span className="text-emerald-400 font-bold">✓ Step {step.step}:</span>
                            <span className="text-amber-300 font-semibold">{step.action}</span>
                            <span className="text-gray-400">➔ {step.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Answer Content */}
                  {msg.role === 'assistant' ? (
                    <MarkdownMessage content={msg.content} />
                  ) : (
                    <div className="whitespace-pre-line text-xs">{msg.content}</div>
                  )}

                  {/* Copy the answer out for a case note or filing */}
                  {msg.role === 'assistant' && msg.responseObj && (
                    <div className="flex justify-end mt-2">
                      <button
                        onClick={() => {
                          navigator.clipboard?.writeText(msg.content);
                          setCopiedIdx(idx);
                          setTimeout(() => setCopiedIdx(c => (c === idx ? null : c)), 1500);
                        }}
                        className="flex items-center space-x-1 text-[10px] text-gray-400 hover:text-white transition-colors"
                      >
                        {copiedIdx === idx ? (
                          <><Check className="w-3 h-3 text-emerald-400" /><span>Copied</span></>
                        ) : (
                          <><Copy className="w-3 h-3" /><span>Copy answer</span></>
                        )}
                      </button>
                    </div>
                  )}

                  {/* Clarification Dialog if Ambiguous */}
                  {msg.responseObj?.is_ambiguous && (
                    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                      <div className="flex items-center space-x-1.5 text-amber-400 font-bold text-[11px] mb-2">
                        <HelpCircle className="w-4 h-4" />
                        <span>Disambiguation Options</span>
                      </div>
                      <div className="space-y-1.5">
                        {msg.responseObj.clarification_options.map((opt, oIdx) => (
                          <button
                            key={oIdx}
                            onClick={() => handleSend(`Tell me about ${opt.split('(')[0].trim()}`)}
                            className="w-full text-left p-2 bg-dark-900 hover:bg-amber-500/20 border border-amber-500/20 rounded text-[11px] text-gray-200 hover:text-white transition-colors"
                          >
                            👉 {opt}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source Independence Analysis Card */}
                  {msg.responseObj?.source_independence && (
                    <div className="mt-3 p-3 bg-cyan-950/30 border border-cyan-500/40 rounded-lg text-xs space-y-2">
                      <div className="flex items-center space-x-1.5 font-bold text-cyan-300 text-[11px]">
                        <Globe2 className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Source Independence Analysis</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-mono">
                        <div className="p-1.5 bg-dark-900 rounded border border-gray-700">
                          <div className="text-gray-400">Reported Mentions</div>
                          <div className="text-sm font-bold text-white mt-0.5">{msg.responseObj.source_independence.reported_sources_count}</div>
                        </div>
                        <div className="p-1.5 bg-dark-900 rounded border border-emerald-500/40">
                          <div className="text-emerald-400 font-bold">Likely Independent</div>
                          <div className="text-sm font-bold text-emerald-300 mt-0.5">{msg.responseObj.source_independence.independent_sources_count}</div>
                        </div>
                        <div className="p-1.5 bg-dark-900 rounded border border-amber-500/40">
                          <div className="text-amber-400 font-bold">Derivative Replicas</div>
                          <div className="text-sm font-bold text-amber-300 mt-0.5">{msg.responseObj.source_independence.derivative_sources_count}</div>
                        </div>
                      </div>
                      <div className="text-[10px] text-gray-400 font-mono">
                        Primary Origin: <span className="text-gray-200">{msg.responseObj.source_independence.primary_origin}</span>
                      </div>
                    </div>
                  )}

                  {/* Citations Card Section */}
                  {msg.responseObj?.citations && msg.responseObj.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-700/60">
                      <div className="flex items-center justify-between text-[11px] font-bold text-emerald-400 uppercase tracking-wider mb-2">
                        <div className="flex items-center space-x-1.5">
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Verified Evidence Citations ({msg.responseObj.citations.length})</span>
                        </div>
                        {onOpenDocumentViewer && (
                          <button
                            onClick={onOpenDocumentViewer}
                            className="text-[10px] text-indigo-400 hover:underline capitalize font-normal flex items-center space-x-1"
                          >
                            <span>Open in Doc Viewer</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                      <div className="grid grid-cols-1 gap-2">
                        {msg.responseObj.citations.map((cite, cIdx) => (
                          <div key={cIdx} className="p-2.5 bg-dark-900 rounded-lg border border-gray-700 text-[11px]">
                            <div className="flex items-center justify-between text-[10px] text-gray-400 mb-1">
                              <span className="font-mono text-indigo-400 font-semibold">{cite.evidence_id}</span>
                              <span className="text-gray-400">{cite.reference_location}</span>
                            </div>
                            <div className="font-semibold text-gray-200">{cite.source_title}</div>
                            <div className="text-gray-400 mt-1 italic font-serif">"{cite.quote_or_claim}"</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Contradicting Evidence Banner */}
                  {msg.responseObj?.counter_evidence && msg.responseObj.counter_evidence.length > 0 && (
                    <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                      <div className="flex items-center space-x-1.5 text-red-400 font-bold text-[11px] mb-1.5">
                        <ShieldAlert className="w-4 h-4" />
                        <span>Contradicting Evidence & Discrepancies</span>
                      </div>
                      {msg.responseObj.counter_evidence.map((ce, ceIdx) => (
                        <div key={ceIdx} className="text-[11px] space-y-1">
                          <div className="font-semibold text-red-300">⚠️ {ce.source}:</div>
                          <div className="text-gray-300">Statement: {ce.claim}</div>
                          <div className="text-amber-300 font-medium">Discrepancy: {ce.discrepancy}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Evidence Gaps */}
                  {msg.responseObj?.evidence_gaps && msg.responseObj.evidence_gaps.length > 0 && (
                    <div className="mt-3 p-2.5 bg-gray-800/60 rounded-lg border border-gray-700/60 text-[11px]">
                      <div className="text-amber-400 font-bold mb-1">🔍 Identified Evidence Gaps:</div>
                      <ul className="list-disc list-inside text-gray-400 space-y-0.5">
                        {msg.responseObj.evidence_gaps.map((gap, gIdx) => (
                          <li key={gIdx}>{gap}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Conversational Follow-Up Suggestion Pills */}
                  {msg.responseObj?.suggested_next_steps && msg.responseObj.suggested_next_steps.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-gray-700/60 space-y-1.5">
                      <div className="text-[10px] uppercase font-bold text-gray-400">Suggested Follow-Up Interrogations:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.responseObj.suggested_next_steps.map((step, sIdx) => {
                          const actionText = step.includes("'") ? step.split("'")[1] : step;
                          return (
                            <button
                              key={sIdx}
                              onClick={() => handleSend(actionText)}
                              className="text-[11px] bg-dark-900 hover:bg-indigo-600/30 border border-indigo-500/30 hover:border-indigo-400 text-indigo-300 hover:text-white px-2.5 py-1 rounded-full font-semibold transition-colors flex items-center space-x-1"
                            >
                              <span>👉 {step}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Full record set, rendered inline rather than sent elsewhere */}
                  {msg.responseObj?.detail_sections && msg.responseObj.detail_sections.length > 0 && (
                    <DetailSections
                      sections={msg.responseObj.detail_sections}
                      stats={msg.responseObj.detail_stats}
                    />
                  )}

                  {/* Trigger Visual Highlight Action Button & Network Scope Card */}
                  {msg.responseObj?.visual_actions && (
                    <div className="mt-3 p-2.5 bg-indigo-950/30 border border-indigo-500/40 rounded-lg space-y-2">
                      <div className="flex items-center justify-between text-[11px]">
                        <div className="flex items-center space-x-1.5 text-indigo-300 font-bold">
                          <CornerDownRight className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Graph & Map Synchronization</span>
                        </div>
                        <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono border border-indigo-500/30">
                          {msg.responseObj.visual_actions.node_ids?.length || 0} Nodes Mapped
                        </span>
                      </div>

                      <div className="text-[11px] text-gray-300 font-medium">
                        {msg.responseObj.visual_actions.description}
                      </div>

                      {msg.responseObj.visual_actions.node_ids && msg.responseObj.visual_actions.node_ids.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {msg.responseObj.visual_actions.node_ids.slice(0, 10).map((nId, nIdx) => (
                            <span key={nIdx} className="text-[9px] bg-dark-900 border border-indigo-500/30 text-indigo-300 px-1.5 py-0.5 rounded font-mono">
                              🔗 {nId}
                            </span>
                          ))}
                          {msg.responseObj.visual_actions.node_ids.length > 10 && (
                            <span className="text-[9px] bg-dark-900 border border-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">
                              +{msg.responseObj.visual_actions.node_ids.length - 10} more
                            </span>
                          )}
                        </div>
                      )}

                      <button
                        onClick={() => onTriggerVisualHighlight(msg.responseObj!.visual_actions!, { navigate: true })}
                        className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white py-1.5 px-3 rounded-lg text-xs font-semibold shadow-md transition-all mt-1"
                      >
                        <span>🌐 Focus Network on Knowledge Graph & Map</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center space-x-2 text-xs text-gray-400 bg-dark-800 p-3 rounded-lg w-fit border border-gray-700">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-spin" />
                <span>{fullDetail ? 'Compiling the full case record set across Graph, DB, evidence & telemetry...' : 'Executing Dynamic Query Plan across Graph, DB & Telemetry...'}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar with Voice Microphone */}
          <div className="p-3 border-t border-gray-800 bg-dark-800/90">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center space-x-2"
            >
              <input
                type="text"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder={fullDetail ? 'Full Info is on - ask anything and the whole record set comes with the answer...' : 'Ask any open-ended investigation question, or say "give me the full brief"...'}
                className="flex-1 bg-dark-900 border border-gray-700 rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
              />

              <button
                type="button"
                onClick={toggleVoiceRecording}
                className={`p-2 rounded-lg transition-colors border ${
                  isRecording
                    ? 'bg-red-600 text-white animate-pulse border-red-400'
                    : 'bg-dark-900 text-gray-400 hover:text-white border-gray-700'
                }`}
                title={isRecording ? 'Listening...' : 'Voice Query (Speech-to-Text)'}
              >
                {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>

              <button
                type="submit"
                disabled={isLoading || !inputQuery.trim()}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white p-2 rounded-lg transition-colors shadow"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </>
      ) : (
        /* Competing Hypothesis Generator Screen */
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <div className="flex items-center space-x-2">
            <Scale className="w-5 h-5 text-amber-400" />
            <h4 className="text-sm font-bold text-white">Automated Investigative Theory & Hypothesis Evaluation</h4>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {hypotheses.map((hyp) => (
              <div key={hyp.hypothesis_id} className="p-5 bg-dark-800 border border-gray-700 rounded-2xl space-y-3 shadow-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-indigo-400">{hyp.hypothesis_id}</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] text-gray-400">Confidence Probability:</span>
                    <span className="text-xs font-bold text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/30">
                      {Math.round(hyp.probability_score * 100)}%
                    </span>
                  </div>
                </div>

                <h5 className="text-sm font-bold text-white">{hyp.title}</h5>
                <p className="text-xs text-gray-300 leading-relaxed">{hyp.summary}</p>

                {/* Supporting & Contradicting Grid */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 bg-emerald-950/20 border border-emerald-500/30 rounded-xl space-y-1">
                    <div className="text-[10px] font-bold text-emerald-400 uppercase">Supporting Evidence</div>
                    <ul className="list-disc list-inside text-xs text-gray-300 space-y-1">
                      {hyp.supporting_evidence.map((se: string, idx: number) => (
                        <li key={idx}>{se}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="p-3 bg-red-950/20 border border-red-500/30 rounded-xl space-y-1">
                    <div className="text-[10px] font-bold text-red-400 uppercase">Contradicting Evidence</div>
                    <ul className="list-disc list-inside text-xs text-gray-300 space-y-1">
                      {hyp.contradicting_evidence.map((ce: string, idx: number) => (
                        <li key={idx}>{ce}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
