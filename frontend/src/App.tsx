import React, { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import { CytoscapeGraph } from './components/graph/CytoscapeGraph';
import { InvestigatorMap } from './components/map/InvestigatorMap';
import { InvestigatorTimeline } from './components/timeline/InvestigatorTimeline';
import { UniversalAIInvestigator } from './components/ai/UniversalAIInvestigator';
import { EvidenceVault } from './components/evidence/EvidenceVault';
import { AnalyticsPanel } from './components/analytics/AnalyticsPanel';
import { IngestionHub } from './components/ingestion/IngestionHub';
import { OSINTModal } from './components/osint/OSINTModal';
import { DocumentViewerModal } from './components/documents/DocumentViewerModal';
import { CourtDossierModal } from './components/court/CourtDossierModal';
import { EntityResolutionModal } from './components/resolution/EntityResolutionModal';
import type { Case, GraphData, MapEvent, TimelineEvent, GraphNode, HighlightAction, EvidenceItem } from './types';
import { api } from './lib/api';

import { Sparkles, X } from 'lucide-react';

export const App: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string>('CASE-2024-8812');
  const [activeTab, setActiveTab] = useState<string>('workspace');
  const [isReseeding, setIsReseeding] = useState<boolean>(false);
  const [isCopilotDrawerOpen, setIsCopilotDrawerOpen] = useState<boolean>(false);

  // Synchronized Workspace State
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [], stats: { total_nodes: 0, total_edges: 0, hubs_count: 0, bridges_count: 0 } });
  const [mapEvents, setMapEvents] = useState<MapEvent[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);
  const [highlightedCoords, setHighlightedCoords] = useState<number[][]>([]);
  const [activeTimeFilter, setActiveTimeFilter] = useState<string | null>(null);

  // Modals
  const [osintNode, setOsintNode] = useState<GraphNode | null>(null);
  const [isDocViewerOpen, setIsDocViewerOpen] = useState(false);
  const [isDossierOpen, setIsDossierOpen] = useState(false);
  const [isResolutionOpen, setIsResolutionOpen] = useState(false);

  // Initial Data Fetch
  const loadCaseData = async (caseId: string) => {
    try {
      const [casesList, gData, mEvents, tEvents, evData] = await Promise.all([
        api.getCases(),
        api.getGraph(caseId),
        api.getMapEvents(caseId),
        api.getTimeline(caseId),
        api.getEvidence(caseId)
      ]);

      setCases(casesList);
      setGraphData(gData);
      setMapEvents(mEvents);
      setTimelineEvents(tEvents);
      setEvidenceList(evData);
    } catch (err) {
      console.error('Error fetching initial case data:', err);
    }
  };

  useEffect(() => {
    loadCaseData(activeCaseId);
  }, [activeCaseId]);

  // Handle Reseed
  const handleReseed = async () => {
    setIsReseeding(true);
    try {
      await api.reseedData();
      await loadCaseData(activeCaseId);
    } catch (e) {
      console.error(e);
    } finally {
      setIsReseeding(false);
    }
  };

  // Synchronized Event Handlers
  const handleSelectGraphNode = (node: GraphNode | null) => {
    if (!node) {
      setSelectedNodeId(null);
      setHighlightedCoords([]);
      return;
    }
    setSelectedNodeId(node.id);

    // Find linked map events
    const matchingEvents = mapEvents.filter(e => e.related_entities.includes(node.id));
    if (matchingEvents.length > 0) {
      setHighlightedCoords(matchingEvents.map(e => [e.latitude, e.longitude]));
      setSelectedEventId(matchingEvents[0].event_id);
    }
  };

  const handleSelectEntityByName = (name: string) => {
    const match = graphData.nodes.find(n => n.label.toLowerCase().includes(name.toLowerCase()) || name.toLowerCase().includes(n.label.toLowerCase()));
    if (match) {
      handleSelectGraphNode(match);
      setActiveTab('workspace');
    }
  };

  const handleSelectMapEvent = (event: MapEvent | null) => {
    if (!event) {
      setSelectedEventId(null);
      return;
    }
    setSelectedEventId(event.event_id);

    // Highlight linked entities in graph
    if (event.related_entities.length > 0) {
      setSelectedNodeId(event.related_entities[0]);
      setHighlightedNodeIds(event.related_entities);
    }
  };

  const handleSelectTimelineEvent = (event: TimelineEvent | null) => {
    if (!event) {
      setSelectedEventId(null);
      return;
    }
    setSelectedEventId(event.id);

    if (event.latitude && event.longitude) {
      setHighlightedCoords([[event.latitude, event.longitude]]);
    }
    if (event.related_entities.length > 0) {
      setSelectedNodeId(event.related_entities[0]);
      setHighlightedNodeIds(event.related_entities);
    }
  };

  const handleTriggerVisualHighlight = (
    action: HighlightAction,
    options?: { navigate?: boolean }
  ) => {
    if (action.node_ids && action.node_ids.length > 0) {
      setHighlightedNodeIds(action.node_ids);
      setSelectedNodeId(action.node_ids[0]);
    }
    if (action.coordinates && action.coordinates.length > 0) {
      setHighlightedCoords(action.coordinates);
    }
    if (action.event_ids && action.event_ids.length > 0) {
      setSelectedEventId(action.event_ids[0]);
    }
    // Highlights apply silently; only an explicit "focus" click moves the user to
    // the workspace. Jumping on every answer used to yank the investigator away
    // from the reply they just asked for.
    if (options?.navigate !== false) {
      setActiveTab('workspace');
    }
  };

  const currentCase = cases.find(c => c.case_id === activeCaseId) || {
    case_id: activeCaseId,
    title: 'Operation ShadowNet: Hawala Syndicate & Inter-State Smuggling',
    classification: 'RESTRICTED',
    status: 'ACTIVE',
    lead_investigator: 'Inspector Rajiv Sen',
    assigned_team: ['rajiv_sen'],
    created_at: new Date().toISOString()
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-dark-900 text-gray-100 overflow-hidden select-none">
      {/* Top Navigation Header */}
      <Header
        cases={cases}
        activeCaseId={activeCaseId}
        onSelectCase={setActiveCaseId}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onReseed={handleReseed}
        isReseeding={isReseeding}
        onOpenDocViewer={() => setIsDocViewerOpen(true)}
        onOpenResolution={() => setIsResolutionOpen(true)}
        onOpenDossier={() => setIsDossierOpen(true)}
      />

      {/* Main Workspace Body */}
      <main className="flex-1 overflow-hidden p-3">
        {activeTab === 'workspace' && (
          <div className="h-full flex flex-col space-y-3 relative">
            {/* Top Tri-View Split: Network Graph (Left) & Actual Map (Right) */}
            <div className="flex-1 grid grid-cols-12 gap-3 min-h-0">
              {/* Left Column: Cytoscape Network Graph (60%) */}
              <div className="col-span-7 h-full rounded-xl overflow-hidden border border-gray-800 shadow-xl bg-dark-900">
                <CytoscapeGraph
                  graphData={graphData}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={handleSelectGraphNode}
                  onOpenOSINT={(node) => setOsintNode(node)}
                  highlightedNodeIds={highlightedNodeIds}
                  onPathDiscovered={(nodeIds) => setHighlightedNodeIds(nodeIds)}
                />
              </div>

              {/* Right Column: Actual Interactive Map (40%) */}
              <div className="col-span-5 h-full rounded-xl overflow-hidden border border-gray-800 shadow-xl bg-dark-900">
                <InvestigatorMap
                  events={mapEvents}
                  selectedEventId={selectedEventId}
                  onSelectEvent={handleSelectMapEvent}
                  highlightedCoords={highlightedCoords}
                />
              </div>
            </div>

            {/* Bottom: Synchronized Chronological Timeline (Height 175px) */}
            <div className="h-44 flex-shrink-0 rounded-xl overflow-hidden border border-gray-800 shadow-xl">
              <InvestigatorTimeline
                events={timelineEvents}
                selectedEventId={selectedEventId}
                onSelectEvent={handleSelectTimelineEvent}
                activeTimeFilter={activeTimeFilter}
                onTimeFilterChange={setActiveTimeFilter}
              />
            </div>

            {/* Floating Live AI Copilot Launcher Button */}
            <button
              onClick={() => setIsCopilotDrawerOpen(!isCopilotDrawerOpen)}
              className="absolute bottom-48 right-4 z-30 flex items-center space-x-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white px-3.5 py-2 rounded-full shadow-2xl border border-indigo-400/40 text-xs font-bold transition-all transform hover:scale-105"
            >
              <Sparkles className="w-4 h-4 animate-pulse text-amber-300" />
              <span>{isCopilotDrawerOpen ? 'Hide Live Copilot' : 'AI Copilot (Live Network Sync)'}</span>
            </button>

            {/* Embedded Live Copilot Slide-Over Drawer */}
            {isCopilotDrawerOpen && (
              <div className="absolute top-0 right-0 w-[450px] h-full z-40 bg-dark-950/95 backdrop-blur-md border-l border-indigo-500/40 shadow-2xl rounded-r-xl flex flex-col transition-all">
                <div className="p-3 bg-dark-900/90 border-b border-gray-800 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-bold text-white">Live Investigation Copilot</span>
                    <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono">
                      Real-Time Sync
                    </span>
                  </div>
                  <button
                    onClick={() => setIsCopilotDrawerOpen(false)}
                    className="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-white transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-hidden p-2">
                  <UniversalAIInvestigator
                    activeCaseId={activeCaseId}
                    onTriggerVisualHighlight={handleTriggerVisualHighlight}
                    onOpenDocumentViewer={() => setIsDocViewerOpen(true)}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Kept mounted so the investigation transcript survives a trip to the
            workspace and back - a full brief is worth returning to. */}
        <div className={activeTab === 'ai' ? 'h-full' : 'hidden'}>
          <UniversalAIInvestigator
            activeCaseId={activeCaseId}
            onTriggerVisualHighlight={handleTriggerVisualHighlight}
            onOpenDocumentViewer={() => setIsDocViewerOpen(true)}
          />
        </div>

        {activeTab === 'evidence' && (
          <EvidenceVault activeCaseId={activeCaseId} />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsPanel
            activeCaseId={activeCaseId}
            onTriggerVisualHighlight={handleTriggerVisualHighlight}
          />
        )}

        {activeTab === 'ingestion' && (
          <IngestionHub
            activeCaseId={activeCaseId}
            onRefresh={() => loadCaseData(activeCaseId)}
          />
        )}
      </main>

      {/* Controlled OSINT Enrichment Modal */}
      <OSINTModal
        node={osintNode}
        activeCaseId={activeCaseId}
        onClose={() => setOsintNode(null)}
      />

      {/* Document Intelligence & OCR Annotation Viewer Modal */}
      <DocumentViewerModal
        isOpen={isDocViewerOpen}
        onClose={() => setIsDocViewerOpen(false)}
        onSelectEntityByName={handleSelectEntityByName}
      />

      {/* Court-Admissible Case Dossier Modal */}
      <CourtDossierModal
        isOpen={isDossierOpen}
        onClose={() => setIsDossierOpen(false)}
        currentCase={currentCase}
        timelineEvents={timelineEvents}
        evidenceList={evidenceList}
      />

      {/* Entity Resolution & Merge Studio Modal */}
      <EntityResolutionModal
        isOpen={isResolutionOpen}
        onClose={() => setIsResolutionOpen(false)}
        onMerged={() => loadCaseData(activeCaseId)}
      />
    </div>
  );
};

export default App;
