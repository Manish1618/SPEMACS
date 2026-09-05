import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import type { Core } from 'cytoscape';
import type { GraphData, GraphNode } from '../../types';
import { ZoomIn, ZoomOut, Maximize2, Globe, Search, Route, Sparkles, Download } from 'lucide-react';
import { api } from '../../lib/api';

interface CytoscapeGraphProps {
  graphData: GraphData;
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode | null) => void;
  onOpenOSINT: (node: GraphNode) => void;
  highlightedNodeIds: string[];
  onPathDiscovered?: (nodeIds: string[], coords?: number[][]) => void;
}

export const CytoscapeGraph: React.FC<CytoscapeGraphProps> = ({
  graphData,
  selectedNodeId,
  onSelectNode,
  onOpenOSINT,
  highlightedNodeIds,
  onPathDiscovered
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [currentLayout, setCurrentLayout] = useState('cose');

  // Shortest Path Studio State
  const [showPathStudio, setShowPathStudio] = useState(false);
  const [sourceNodeId, setSourceNodeId] = useState<string>('ENT-PER-01'); // Vikram Malhotra default
  const [targetNodeId, setTargetNodeId] = useState<string>('ENT-ACC-03'); // Swiss Account default
  const [pathResult, setPathResult] = useState<any | null>(null);
  const [isSearchingPath, setIsSearchingPath] = useState(false);

  // The API emits entity types in upper case (PERSON, PHONE, ...). Matching on
  // title case silently fell through to the grey default for every node.
  const getNodeColor = (type: string) => {
    switch ((type || '').toUpperCase()) {
      case 'PERSON': return '#6366F1'; // Indigo
      case 'PHONE': return '#10B981'; // Emerald
      case 'VEHICLE': return '#F59E0B'; // Amber
      case 'ORGANIZATION': return '#8B5CF6'; // Purple
      case 'LOCATION': return '#EF4444'; // Red
      case 'ACCOUNT': return '#06B6D4'; // Cyan
      case 'CASE': return '#3B82F6'; // Blue
      default: return '#9CA3AF';
    }
  };

  // How many nodes of each type are actually in the case, for the filter labels.
  const typeCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    graphData.nodes.forEach(n => {
      const key = (n.entity_type || '').toUpperCase();
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }, [graphData]);

  // The filter picks a focus set, but phones do not link to phones and accounts do
  // not link to accounts - keeping only the matches would strand every node with no
  // edges at all. So the focus set is drawn together with whatever it is directly
  // connected to, and that context is dimmed so the focus still reads.
  const visibleGraph = React.useMemo(() => {
    const focusNodes = graphData.nodes.filter(n => {
      if (filterType !== 'ALL' && (n.entity_type || '').toUpperCase() !== filterType) return false;
      if (searchTerm && !n.label.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
    const focusSet = new Set(focusNodes.map(n => n.id));
    const isFiltered = filterType !== 'ALL' || searchTerm.trim().length > 0;

    const contextSet = new Set<string>();
    if (isFiltered) {
      graphData.edges.forEach(e => {
        if (focusSet.has(e.source) && !focusSet.has(e.target)) contextSet.add(e.target);
        if (focusSet.has(e.target) && !focusSet.has(e.source)) contextSet.add(e.source);
      });
    }

    const visibleNodes = graphData.nodes.filter(n => focusSet.has(n.id) || contextSet.has(n.id));
    const nodeSet = new Set(visibleNodes.map(n => n.id));
    const filteredEdges = graphData.edges.filter(
      e => nodeSet.has(e.source) && nodeSet.has(e.target)
    );

    return { focusSet, contextSet, visibleNodes, filteredEdges, isFiltered };
  }, [graphData, filterType, searchTerm]);

  const initCytoscape = (layoutName: string) => {
    if (!containerRef.current) return;

    const { focusSet, visibleNodes, filteredEdges } = visibleGraph;

    const elements = [
      ...visibleNodes.map(n => ({
        data: {
          id: n.id,
          label: n.label,
          type: n.entity_type,
          is_bridge: n.is_bridge,
          is_hub: n.is_hub,
          is_context: !focusSet.has(n.id),
          centrality: n.centrality_score,
          raw: n
        },
        classes: focusSet.has(n.id) ? '' : 'context-node'
      })),
      ...filteredEdges.map(e => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          rel_type: e.relationship_type,
          confidence: e.confidence || 1.0,
          raw: e
        }
      }))
    ];

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#F3F4F6',
            'font-size': '11px',
            'font-weight': 600,
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'background-color': (ele: any) => getNodeColor(ele.data('type')),
            'width': (ele: any) => ele.data('is_hub') ? 44 : (ele.data('is_bridge') ? 40 : 32),
            'height': (ele: any) => ele.data('is_hub') ? 44 : (ele.data('is_bridge') ? 40 : 32),
            'border-width': (ele: any) => (ele.data('is_bridge') || ele.data('is_hub')) ? 3.5 : 1.5,
            'border-color': (ele: any) => ele.data('is_bridge') ? '#F59E0B' : (ele.data('is_hub') ? '#3B82F6' : '#1F2937'),
            'overlay-opacity': 0
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#4B5563',
            'target-arrow-color': '#4B5563',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#9CA3AF',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'arrow-scale': 0.8
          }
        },
        {
          // One-hop context: present so the connections are visible, muted so it
          // is obvious these are not what was filtered for.
          selector: '.context-node',
          style: {
            'opacity': 0.45,
            'width': 22,
            'height': 22,
            'font-size': '9px',
            'color': '#9CA3AF'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#FFFFFF'
          }
        },
        {
          selector: '.highlighted',
          style: {
            'border-width': 5,
            'border-color': '#F59E0B'
          }
        },
        {
          selector: '.path-edge',
          style: {
            'line-color': '#F59E0B',
            'target-arrow-color': '#F59E0B',
            'width': 3.5
          }
        }
      ],
      layout: {
        name: layoutName,
        animate: false,
        padding: 45,
        nodeRepulsion: () => 4800,
        idealEdgeLength: () => 95
      } as any
    });

    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data('raw');
      onSelectNode(nodeData);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode(null);
      }
    });

    cyRef.current = cy;
  };

  useEffect(() => {
    initCytoscape(currentLayout);
    return () => {
      if (cyRef.current) {
        try {
          cyRef.current.destroy();
        } catch (e) {
          console.warn('Cytoscape destroy warning:', e);
        }
        cyRef.current = null;
      }
    };
  }, [graphData, filterType, searchTerm, currentLayout]);


  // Handle selected node update & highlights
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    cy.nodes().removeClass('highlighted');
    cy.edges().removeClass('path-edge');

    if (selectedNodeId) {
      const target = cy.getElementById(selectedNodeId);
      if (target.length > 0) {
        target.select();
        cy.center(target);
      }
    } else {
      cy.nodes().unselect();
    }

    if (highlightedNodeIds && highlightedNodeIds.length > 0) {
      highlightedNodeIds.forEach(id => {
        cy.getElementById(id).addClass('highlighted');
      });
    }
  }, [selectedNodeId, highlightedNodeIds]);

  // Handle Shortest Path Execution
  const handleTracePath = async () => {
    if (!sourceNodeId || !targetNodeId || sourceNodeId === targetNodeId) return;
    setIsSearchingPath(true);
    setPathResult(null);

    try {
      const res = await api.getShortestPath(sourceNodeId, targetNodeId);
      setPathResult(res);

      if (res.path_found && cyRef.current) {
        const cy = cyRef.current;
        cy.nodes().removeClass('highlighted');
        cy.edges().removeClass('path-edge');

        const pathIds: string[] = res.path_node_ids || [];
        pathIds.forEach(id => {
          cy.getElementById(id).addClass('highlighted');
        });

        // Highlight intermediate edges
        for (let i = 0; i < pathIds.length - 1; i++) {
          const u = pathIds[i];
          const v = pathIds[i+1];
          const edges = cy.edges(`[source = "${u}"][target = "${v}"], [source = "${v}"][target = "${u}"]`);
          edges.addClass('path-edge');
        }

        // Inform workspace synchronizer
        if (onPathDiscovered) {
          onPathDiscovered(pathIds);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearchingPath(false);
    }
  };

  const handleExportPNG = () => {
    if (!cyRef.current) return;
    const png64 = cyRef.current.png({ full: true, scale: 2, bg: '#0B0F17' });
    const link = document.createElement('a');
    link.download = `SPEMASS_Graph_Export_${Date.now()}.png`;
    link.href = png64;
    link.click();
  };

  const selectedNodeObj = graphData.nodes.find(n => n.id === selectedNodeId);

  return (
    <div className="relative w-full h-full bg-dark-900 overflow-hidden flex flex-col">
      {/* Top Main Toolbar */}
      <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center space-x-2 pointer-events-auto bg-dark-800/90 backdrop-blur-md p-1.5 rounded-lg border border-gray-700/70 shadow-lg">
          <div className="flex items-center space-x-1.5 px-2 py-1 bg-dark-900 rounded border border-gray-700">
            <Search className="w-3.5 h-3.5 text-gray-400" />
            <input
              type="text"
              placeholder="Filter node..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-transparent text-xs text-gray-200 focus:outline-none w-28"
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            aria-label="Filter by Entity Type"
            className="bg-dark-900 border border-gray-700 text-xs text-gray-300 rounded px-2 py-1 focus:outline-none"
          >
            <option value="ALL">All Types ({graphData.nodes.length})</option>
            <option value="PERSON">Persons ({typeCounts.PERSON || 0})</option>
            <option value="PHONE">Phones ({typeCounts.PHONE || 0})</option>
            <option value="VEHICLE">Vehicles ({typeCounts.VEHICLE || 0})</option>
            <option value="ORGANIZATION">Organizations ({typeCounts.ORGANIZATION || 0})</option>
            <option value="ACCOUNT">Accounts ({typeCounts.ACCOUNT || 0})</option>
            <option value="LOCATION">Locations ({typeCounts.LOCATION || 0})</option>
          </select>

          {/* Shortest Path Studio Toggle Button */}
          <button
            onClick={() => setShowPathStudio(!showPathStudio)}
            className={`flex items-center space-x-1 text-xs px-2.5 py-1 rounded font-semibold transition-colors border ${
              showPathStudio
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-dark-900 text-gray-300 border-gray-700 hover:text-white'
            }`}
          >
            <Route className="w-3.5 h-3.5 text-amber-400" />
            <span>Link Path Tool</span>
          </button>
        </div>

        {/* Right Tools: Layout Switcher, PNG Export & Zoom */}
        <div className="flex items-center space-x-2 pointer-events-auto bg-dark-800/90 backdrop-blur-md p-1 rounded-lg border border-gray-700/70 shadow-lg">
          <select
            value={currentLayout}
            onChange={(e) => setCurrentLayout(e.target.value)}
            aria-label="Graph Layout"
            className="bg-dark-900 border border-gray-700 text-xs text-gray-300 rounded px-2 py-1 focus:outline-none"
          >
            <option value="cose">CoSE Force-Directed</option>
            <option value="concentric">Concentric Hierarchy</option>
            <option value="circle">Circular</option>
            <option value="breadthfirst">Breadthfirst Tree</option>
          </select>

          <button
            onClick={handleExportPNG}
            className="p-1.5 hover:bg-gray-700 rounded text-gray-300 hover:text-white"
            title="Export High-Res Graph PNG"
          >
            <Download className="w-4 h-4" />
          </button>

          <div className="h-4 w-px bg-gray-700" />

          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)}
            className="p-1.5 hover:bg-gray-700 rounded text-gray-300 hover:text-white"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            className="p-1.5 hover:bg-gray-700 rounded text-gray-300 hover:text-white"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.fit(undefined, 40)}
            className="p-1.5 hover:bg-gray-700 rounded text-gray-300 hover:text-white"
            title="Reset Fit"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Floating Shortest Path Studio Panel */}
      {showPathStudio && (
        <div className="absolute top-16 left-3 z-20 bg-dark-800/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-4 shadow-2xl w-84 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-400">
              <Route className="w-4 h-4" />
              <span>Multi-Hop Shortest Path Finder</span>
            </div>
            <button
              onClick={() => setShowPathStudio(false)}
              className="text-gray-400 hover:text-gray-200 text-xs"
            >
              ✕
            </button>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <label className="block text-[10px] uppercase font-bold text-gray-400 mb-1">Source Entity (Origin)</label>
              <select
                value={sourceNodeId}
                onChange={(e) => setSourceNodeId(e.target.value)}
                className="w-full bg-dark-900 border border-gray-700 rounded px-2 py-1.5 text-gray-200 focus:outline-none text-xs"
              >
                {graphData.nodes.map(n => (
                  <option key={n.id} value={n.id}>{n.label} ({n.entity_type})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-gray-400 mb-1">Target Entity (Destination)</label>
              <select
                value={targetNodeId}
                onChange={(e) => setTargetNodeId(e.target.value)}
                className="w-full bg-dark-900 border border-gray-700 rounded px-2 py-1.5 text-gray-200 focus:outline-none text-xs"
              >
                {graphData.nodes.map(n => (
                  <option key={n.id} value={n.id}>{n.label} ({n.entity_type})</option>
                ))}
              </select>
            </div>

            <button
              onClick={handleTracePath}
              disabled={isSearchingPath}
              className="w-full bg-amber-600 hover:bg-amber-500 text-white font-bold py-1.5 px-3 rounded transition-colors text-xs flex items-center justify-center space-x-1.5 shadow"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isSearchingPath ? 'Tracing Connection...' : 'Trace Relational Path'}</span>
            </button>
          </div>

          {pathResult && (
            <div className="pt-2 border-t border-gray-700 text-xs">
              {pathResult.path_found ? (
                <div className="space-y-1.5">
                  <div className="text-emerald-400 font-bold flex items-center space-x-1">
                    <span>✓ Path Discovered ({pathResult.path_node_ids?.length - 1} Hops)</span>
                  </div>
                  <div className="text-[11px] text-gray-300 font-mono bg-dark-900 p-2 rounded border border-gray-800">
                    {pathResult.path_node_ids?.join(' ➔ ')}
                  </div>
                </div>
              ) : (
                <div className="text-red-400 font-semibold">{pathResult.message}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Main Cytoscape Canvas */}
      <div ref={containerRef} className="w-full h-full" />

      {/* What a filtered view is showing, and why the faded nodes are there */}
      {visibleGraph.isFiltered && (
        <div className="absolute bottom-3 right-3 z-10 bg-dark-800/95 backdrop-blur-md border border-gray-700 rounded-lg px-3 py-2 text-[10px] shadow-xl">
          {visibleGraph.focusSet.size === 0 ? (
            <span className="text-amber-300 font-semibold">
              No entity matches this filter in {graphData.nodes.length} case nodes.
            </span>
          ) : (
            <span className="text-gray-300">
              <span className="font-bold text-white">{visibleGraph.focusSet.size}</span> matching ·{' '}
              <span className="font-bold text-gray-400">{visibleGraph.contextSet.size}</span> connected (faded) ·{' '}
              <span className="font-bold text-white">{visibleGraph.filteredEdges.length}</span> links
            </span>
          )}
        </div>
      )}

      {/* Selected Entity Card Inspector Overlay */}
      {selectedNodeObj && (
        <div className="absolute bottom-3 left-3 z-10 bg-dark-800/95 backdrop-blur-md border border-gray-700 rounded-xl p-4 shadow-2xl w-80 max-h-72 overflow-y-auto">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center space-x-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: getNodeColor(selectedNodeObj.entity_type) }}
                />
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-gray-400">
                  {selectedNodeObj.entity_type}
                </span>
                {selectedNodeObj.is_bridge && (
                  <span className="text-[9px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-bold border border-amber-500/40">
                    BRIDGE
                  </span>
                )}
                {selectedNodeObj.is_hub && (
                  <span className="text-[9px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-bold border border-blue-500/40">
                    HUB
                  </span>
                )}
              </div>
              <h4 className="text-sm font-bold text-white mt-1">{selectedNodeObj.label}</h4>
              <p className="text-[10px] text-gray-400 font-mono mt-0.5">{selectedNodeObj.id}</p>
            </div>
            <button
              onClick={() => onSelectNode(null)}
              className="text-gray-400 hover:text-gray-200 text-xs"
            >
              ✕
            </button>
          </div>

          <div className="mt-3 pt-2 border-t border-gray-700/60 space-y-1 text-xs">
            {Object.entries(selectedNodeObj.properties || {}).map(([k, v]) => (
              <div key={k} className="flex justify-between text-[11px]">
                <span className="text-gray-400 capitalize">{k.replace('_', ' ')}:</span>
                <span className="text-gray-200 font-medium truncate max-w-[140px]">
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </span>
              </div>
            ))}
          </div>

          {/* Expand with OSINT Button */}
          <div className="mt-3 pt-2 border-t border-gray-700/60 flex space-x-2">
            <button
              onClick={() => onOpenOSINT(selectedNodeObj)}
              className="w-full flex items-center justify-center space-x-1.5 bg-indigo-600/90 hover:bg-indigo-600 text-white text-xs font-semibold py-1.5 px-3 rounded-lg transition-colors shadow"
            >
              <Globe className="w-3.5 h-3.5 text-amber-300" />
              <span>Expand with OSINT</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
