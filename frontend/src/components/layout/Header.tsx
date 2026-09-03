import React from 'react';
import { Shield, Sparkles, Database, FileCheck, Layers, AlertTriangle, RefreshCw, FileText, GitMerge, Printer } from 'lucide-react';
import type { Case } from '../../types';

interface HeaderProps {
  cases: Case[];
  activeCaseId: string;
  onSelectCase: (caseId: string) => void;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onReseed: () => void;
  isReseeding: boolean;
  onOpenDocViewer: () => void;
  onOpenResolution: () => void;
  onOpenDossier: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  cases,
  activeCaseId,
  onSelectCase,
  activeTab,
  onSelectTab,
  onReseed,
  isReseeding,
  onOpenDocViewer,
  onOpenResolution,
  onOpenDossier
}) => {
  const currentCase = cases.find(c => c.case_id === activeCaseId) || cases[0];

  return (
    <header className="border-b border-gray-800 bg-dark-900/95 sticky top-0 z-50 px-6 py-2.5">
      <div className="flex items-center justify-between">
        {/* Left: Brand & Case Selector */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-base tracking-wider text-white">SPEMASS</span>
                <span className="text-[10px] bg-indigo-500/20 text-indigo-400 px-1.5 py-0.5 rounded font-mono border border-indigo-500/30">
                  AI Decision Support
                </span>
              </div>
            </div>
          </div>

          <div className="h-6 w-px bg-gray-800" />

          {/* Case Dropdown */}
          <div className="flex items-center space-x-2">
            <select
              value={activeCaseId}
              onChange={(e) => onSelectCase(e.target.value)}
              aria-label="Active Case"
              className="bg-dark-800 border border-gray-700 text-xs text-gray-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium"
            >
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id} — {c.title}
                </option>
              ))}
            </select>
            {currentCase && (
              <span className={`text-[9px] px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider ${
                currentCase.classification === 'RESTRICTED' 
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                {currentCase.classification}
              </span>
            )}
          </div>
        </div>

        {/* Center: Main Nav Tabs */}
        <nav className="flex items-center space-x-1 bg-dark-800/80 p-1 rounded-lg border border-gray-800">
          <button
            onClick={() => onSelectTab('workspace')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'workspace'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Tri-View Workspace</span>
          </button>

          <button
            onClick={() => onSelectTab('ai')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'ai'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            <span>AI Investigator</span>
          </button>

          <button
            onClick={() => onSelectTab('evidence')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'evidence'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <FileCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Evidence & Blockchain</span>
          </button>

          <button
            onClick={() => onSelectTab('analytics')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'analytics'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>Cross-Case & Anomalies</span>
          </button>

          <button
            onClick={() => onSelectTab('ingestion')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'ingestion'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span>Ingestion & OCR</span>
          </button>
        </nav>

        {/* Right Tools: Doc Viewer, Merge Studio, Court Dossier, Reset */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onOpenDocViewer}
            title="Open Scanned Document & Annotation Viewer"
            className="flex items-center space-x-1 text-xs bg-dark-800 hover:bg-gray-800 border border-gray-700 text-indigo-300 px-2.5 py-1.5 rounded-md transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Doc Viewer</span>
          </button>

          <button
            onClick={onOpenResolution}
            title="Entity Resolution & Merge Studio"
            className="flex items-center space-x-1 text-xs bg-dark-800 hover:bg-gray-800 border border-gray-700 text-amber-300 px-2.5 py-1.5 rounded-md transition-colors"
          >
            <GitMerge className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Entity Merge</span>
          </button>

          <button
            onClick={onOpenDossier}
            title="Generate Court-Admissible Case Dossier"
            className="flex items-center space-x-1 text-xs bg-dark-800 hover:bg-gray-800 border border-gray-700 text-emerald-300 px-2.5 py-1.5 rounded-md transition-colors"
          >
            <Printer className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Court Dossier</span>
          </button>

          <button
            onClick={onReseed}
            disabled={isReseeding}
            title="Reload Operation ShadowNet synthetic dataset"
            className="flex items-center space-x-1 text-xs bg-dark-800 hover:bg-gray-800 border border-gray-700 text-gray-400 px-2 py-1.5 rounded-md transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReseeding ? 'animate-spin text-indigo-400' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
