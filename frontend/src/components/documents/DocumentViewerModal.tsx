import React, { useState } from 'react';
import { FileText, X, CheckCircle, Tag } from 'lucide-react';

interface DocumentViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectEntityByName: (name: string) => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  isOpen,
  onClose,
  onSelectEntityByName
}) => {
  const [selectedDocId, setSelectedDocId] = useState('DOC-FIR-2024-001');

  if (!isOpen) return null;

  const documents = [
    {
      id: 'DOC-FIR-2024-001',
      title: 'First Information Report No. 8812/2024 - Special Cell',
      filename: 'FIR_8812_EconomicOffences.pdf',
      sha256: '74381f70bc2734731802194c798a0875c7432b7194f1c1092e03948b894101e4',
      date: '01/02/2024',
      ocrConfidence: '98.4%',
      content: `FIRST INFORMATION REPORT (Under Section 154 Cr.P.C.)
State: Delhi | District: New Delhi | Police Station: Special Cell / EOW
FIR No: 8812/2024 | Date: 01/02/2024

Acts & Sections: Section 420, 120B IPC r/w Section 13(2) Prevention of Corruption Act and FEMA guidelines.

Brief Allegations: Intelligence sources report that an unorganized financial network led by Vikram Malhotra (also alias 'Vicky') is laundering proceeds through shell corporations. Associated persons include Amit Shahani (Finance Director at Apex Global Logistics) and Rahul Sharma (Courier). On 14-02-2024, a covert coordination meeting is scheduled at Hotel Grand Palace, Aerocity Delhi. Vehicle Toyota Fortuner DL-04-E-5544 registered to Zenith Holdings was observed ferrying contraband documents. Bank Account #9921884102 at Metro National Bank linked to foreign remittances to Alpine Holdings (Zurich, Switzerland).`,
      entities: [
        { text: 'Vikram Malhotra', type: 'Person' },
        { text: 'Vicky', type: 'Person' },
        { text: 'Amit Shahani', type: 'Person' },
        { text: 'Rahul Sharma', type: 'Person' },
        { text: 'Apex Global Logistics', type: 'Organization' },
        { text: 'Hotel Grand Palace', type: 'Location' },
        { text: 'DL-04-E-5544', type: 'Vehicle' },
        { text: 'Zenith Holdings', type: 'Organization' },
        { text: 'Alpine Holdings', type: 'Organization' }
      ]
    },
    {
      id: 'DOC-CCTV-2024-014',
      title: 'Security Surveillance Transcript - Hotel Grand Palace Aerocity',
      filename: 'Aerocity_Hotel_CCTV_Log_Feb14.pdf',
      sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      date: '14/02/2024',
      ocrConfidence: '99.1%',
      content: `SURVEILLANCE LOG: HOTEL GRAND PALACE, AEROCITY, NEW DELHI
Date of Surveillance: 14-02-2024
Camera ID: CAM-04 (Lobby Lounge & Private Dining)
Time 19:15: Vehicle Toyota Fortuner DL-04-E-5544 arrives at main porch. Subject identified as Vikram Malhotra exits vehicle.
Time 19:28: Amit Shahani arrives via private taxi.
Time 19:30: Vikram Malhotra and Amit Shahani sit at Table 12 in the private lounge. Amit hands an encrypted ledger tablet to Vikram.
Time 20:45: Meeting concludes. Both subjects depart separately.
Camera ID: CAM-09 (Valet Parking): Vehicle DL-04-E-5544 departs toward Gurgaon Toll.`,
      entities: [
        { text: 'DL-04-E-5544', type: 'Vehicle' },
        { text: 'Vikram Malhotra', type: 'Person' },
        { text: 'Amit Shahani', type: 'Person' },
        { text: 'Hotel Grand Palace', type: 'Location' }
      ]
    },
    {
      id: 'DOC-WITNESS-2024-002',
      title: 'Witness Statement & Interrogation - Karan Mehra (Driver)',
      filename: 'Witness_Statement_Karan_Mehra.pdf',
      sha256: '8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4',
      date: '18/02/2024',
      ocrConfidence: '97.2%',
      content: `STATEMENT OF WITNESS KARAN MEHRA (S/O S.K. Mehra, Age 34, Chhatarpur Delhi)
Recorded on: 18-02-2024 by Insp. Rajiv Sen

Q: Who hired you to drive the Toyota Fortuner DL-04-E-5544?
A: I work as a personal driver for Zenith Holdings. On 14-02-2024, Vikram Malhotra called me and told me he was currently out of the country in Dubai and that I should deliver the car to Rahul Sharma instead.

Investigator Note: Witness claims Vikram was in Dubai on Feb 14; however, physical CCTV footage (DOC-CCTV-2024-014) and CDR cell tower triangulation place Vikram Malhotra in Delhi at 19:34. This represents a critical factual contradiction.`,
      entities: [
        { text: 'Karan Mehra', type: 'Person' },
        { text: 'DL-04-E-5544', type: 'Vehicle' },
        { text: 'Zenith Holdings', type: 'Organization' },
        { text: 'Vikram Malhotra', type: 'Person' },
        { text: 'Rahul Sharma', type: 'Person' }
      ]
    }
  ];

  const currentDoc = documents.find(d => d.id === selectedDocId) || documents[0];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-dark-900 border border-gray-700 rounded-2xl w-full max-w-5xl h-[88vh] overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-800 bg-dark-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <span>Document Intelligence & In-Browser Annotation Viewer</span>
                <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono border border-indigo-500/30">
                  OCR Grounded
                </span>
              </h3>
              <p className="text-[11px] text-gray-400">Click any highlighted entity pill to jump to the Knowledge Graph</p>
            </div>
          </div>

          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Split */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar: Document List */}
          <div className="w-72 border-r border-gray-800 bg-dark-900/60 p-3 space-y-2 overflow-y-auto">
            <div className="text-[10px] uppercase font-bold text-gray-500 px-2">Case Documents ({documents.length})</div>
            {documents.map(doc => (
              <div
                key={doc.id}
                onClick={() => setSelectedDocId(doc.id)}
                className={`p-3 rounded-lg border transition-all cursor-pointer ${
                  selectedDocId === doc.id
                    ? 'bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/50'
                    : 'bg-dark-800/40 border-gray-800 hover:border-gray-700 hover:bg-dark-800'
                }`}
              >
                <div className="text-xs font-bold text-gray-200 truncate">{doc.title}</div>
                <div className="flex items-center justify-between text-[10px] text-gray-400 font-mono mt-1">
                  <span>{doc.date}</span>
                  <span className="text-emerald-400">OCR: {doc.ocrConfidence}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Right Main Viewer */}
          <div className="flex-1 flex flex-col overflow-hidden bg-dark-950 p-5 space-y-4">
            {/* Doc Metadata Banner */}
            <div className="bg-dark-800/80 border border-gray-700/60 rounded-xl p-3.5 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white">{currentDoc.title}</h4>
                <div className="text-[10px] font-mono text-gray-400 mt-0.5 flex items-center space-x-2">
                  <span>SHA-256: {currentDoc.sha256.slice(0, 24)}...</span>
                  <span>•</span>
                  <span>File: {currentDoc.filename}</span>
                </div>
              </div>

              <div className="flex items-center space-x-2 text-xs">
                <span className="bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded font-mono font-bold border border-emerald-500/30 flex items-center space-x-1">
                  <CheckCircle className="w-3.5 h-3.5" />
                  <span>Verified Hash</span>
                </span>
              </div>
            </div>

            {/* Extracted Entity Badges Ribbon */}
            <div className="bg-dark-900 border border-gray-800 rounded-xl p-3 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-[10px] font-bold text-amber-400 uppercase tracking-wider">
                <Tag className="w-3.5 h-3.5" />
                <span>Extracted Entities (Click to Focus in Graph):</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {currentDoc.entities.map((ent, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      onSelectEntityByName(ent.text);
                      onClose();
                    }}
                    className="text-[11px] bg-dark-800 hover:bg-indigo-600/40 border border-indigo-500/40 hover:border-indigo-400 text-indigo-300 hover:text-white px-2.5 py-1 rounded-full font-semibold transition-all flex items-center space-x-1 shadow"
                  >
                    <span>{ent.text}</span>
                    <span className="text-[9px] text-gray-400">({ent.type})</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Document Content View */}
            <div className="flex-1 overflow-y-auto bg-dark-900 border border-gray-800 rounded-xl p-5 font-mono text-xs text-gray-300 leading-relaxed whitespace-pre-wrap select-text">
              {currentDoc.content}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
