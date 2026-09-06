import React, { useState } from 'react';
import { Upload, CheckCircle2, RefreshCw, AlertTriangle } from 'lucide-react';
import { api, ApiError } from '../../lib/api';

interface IngestionHubProps {
  activeCaseId: string;
  onRefresh: () => void;
}

export const IngestionHub: React.FC<IngestionHubProps> = ({ activeCaseId, onRefresh }) => {
  const [fileTitle, setFileTitle] = useState('');
  const [fileType, setFileType] = useState('PDF_SCAN');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<any | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !fileTitle.trim()) return;

    setIsUploading(true);
    setUploadStatus(null);

    try {
      // Goes through the shared client so the upload carries the caller's token.
      const data = await api.uploadDocument(activeCaseId, fileTitle, fileType, selectedFile);
      setUploadStatus(data);
      setFileTitle('');
      setSelectedFile(null);
      onRefresh();
    } catch (err) {
      setUploadStatus({
        error: err instanceof ApiError ? err.message : 'The upload failed.'
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-500 to-indigo-700 flex items-center justify-center shadow-lg">
            <Upload className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Ingestion, Document OCR & Extraction Hub</span>
            </h3>
            <p className="text-[11px] text-gray-400">Upload case documents, scanned FIRs, CDR records & bank ledgers</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full space-y-6">
        {/* Upload Form */}
        <form onSubmit={handleUpload} className="bg-dark-800 border border-gray-700/80 rounded-2xl p-6 space-y-4 shadow-xl">
          <h4 className="text-sm font-bold text-gray-200 flex items-center space-x-2">
            <span>Upload New Evidence Artifact</span>
          </h4>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">Evidence Title</label>
              <input
                type="text"
                placeholder="e.g. Scanned FIR No. 8812/2024"
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
                required
                className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">Document Type</label>
              <select
                value={fileType}
                onChange={(e) => setFileType(e.target.value)}
                className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="PDF_SCAN">PDF Scan / Investigation Report</option>
                <option value="CSV_CDR">CSV Call Detail Record (CDR)</option>
                <option value="CSV_BANK">CSV Financial Transaction Ledger</option>
                <option value="CSV_TOLL">CSV Toll / ANPR Camera Log</option>
                <option value="IMAGE">CCTV Snapshot / Image</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">Select File</label>
            <input
              type="file"
              onChange={(e) => setSelectedFile(e.target.files ? e.target.files[0] : null)}
              required
              className="w-full bg-dark-900 border border-gray-700 rounded-lg p-2 text-xs text-gray-300 file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer"
            />
          </div>

          <button
            type="submit"
            disabled={isUploading || !selectedFile || !fileTitle.trim()}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold py-2.5 rounded-lg transition-colors flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/20"
          >
            {isUploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Computing SHA-256 & OCR Extracting...</span>
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Ingest, Hash & Anchor to Blockchain</span>
              </>
            )}
          </button>
        </form>

        {/* Upload Success Alert */}
        {uploadStatus?.error && (
          <div className="p-4 bg-red-950/40 border border-red-500/50 rounded-xl flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span className="text-xs text-red-300 leading-relaxed">{uploadStatus.error}</span>
          </div>
        )}

        {uploadStatus && !uploadStatus.error && (
          <div className="p-4 bg-emerald-950/40 border border-emerald-500/50 rounded-xl space-y-2">
            <div className="flex items-center space-x-2 text-emerald-400 font-bold text-xs">
              <CheckCircle2 className="w-4 h-4" />
              <span>{uploadStatus.message}</span>
            </div>
            <div className="text-[11px] font-mono text-gray-300 space-y-1 bg-dark-900/60 p-3 rounded border border-gray-800">
              <div>Document ID: <span className="text-indigo-400">{uploadStatus.document_id}</span></div>
              <div>Evidence ID: <span className="text-indigo-400">{uploadStatus.evidence_id}</span></div>
              <div>SHA-256 Hash: <span className="text-emerald-400">{uploadStatus.sha256_hash}</span></div>
              <div>Blockchain TX: <span className="text-amber-400">{uploadStatus.blockchain_tx_id}</span></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
