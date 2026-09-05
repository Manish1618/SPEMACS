const API_BASE = 'http://localhost:8000/api/v1';

export const api = {
  // Cases
  async getCases() {
    const res = await fetch(`${API_BASE}/cases`);
    return res.json();
  },
  async getCaseById(caseId: string) {
    const res = await fetch(`${API_BASE}/cases/${caseId}`);
    return res.json();
  },

  // Graph
  async getGraph(caseId: string) {
    const res = await fetch(`${API_BASE}/graph/case/${caseId}`);
    return res.json();
  },
  async getKHop(entityId: string, k: number = 2) {
    const res = await fetch(`${API_BASE}/graph/k-hop?entity_id=${encodeURIComponent(entityId)}&k=${k}`);
    return res.json();
  },
  async getShortestPath(sourceId: string, targetId: string) {
    const res = await fetch(`${API_BASE}/graph/shortest-path?source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targetId)}`);
    return res.json();
  },
  async getGraphAnalytics(caseId?: string) {
    const url = caseId ? `${API_BASE}/graph/analytics?case_id=${caseId}` : `${API_BASE}/graph/analytics`;
    const res = await fetch(url);
    return res.json();
  },
  async getCrossCase() {
    const res = await fetch(`${API_BASE}/graph/cross-case`);
    return res.json();
  },
  async getAnomalies() {
    const res = await fetch(`${API_BASE}/graph/anomalies`);
    return res.json();
  },
  async mergeEntities(primaryId: string, duplicateId: string) {
    const res = await fetch(`${API_BASE}/graph/merge-entities?primary_id=${encodeURIComponent(primaryId)}&duplicate_id=${encodeURIComponent(duplicateId)}`, {
      method: 'POST'
    });
    return res.json();
  },

  // Workspace: Map & Timeline
  async getMapEvents(caseId?: string, entityId?: string) {
    let url = `${API_BASE}/workspace/map-events`;
    const params = new URLSearchParams();
    if (caseId) params.append('case_id', caseId);
    if (entityId) params.append('entity_id', entityId);
    if (params.toString()) url += `?${params.toString()}`;
    const res = await fetch(url);
    return res.json();
  },
  async getTimeline(caseId?: string, entityId?: string) {
    let url = `${API_BASE}/workspace/timeline`;
    const params = new URLSearchParams();
    if (caseId) params.append('case_id', caseId);
    if (entityId) params.append('entity_id', entityId);
    if (params.toString()) url += `?${params.toString()}`;
    const res = await fetch(url);
    return res.json();
  },

  // Evidence & Custody
  async getEvidence(caseId?: string) {
    const url = caseId ? `${API_BASE}/evidence?case_id=${caseId}` : `${API_BASE}/evidence`;
    const res = await fetch(url);
    return res.json();
  },
  async getEvidenceDetail(evidenceId: string) {
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}`);
    return res.json();
  },
  async verifyIntegrity(evidenceId: string) {
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}/verify`, { method: 'POST' });
    return res.json();
  },
  async simulateTamper(evidenceId: string) {
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}/simulate-tamper`, { method: 'POST' });
    return res.json();
  },
  async restoreClean(evidenceId: string) {
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}/restore-clean`, { method: 'POST' });
    return res.json();
  },

  // Universal AI Investigator
  // detailLevel 'full' keeps the focused answer and attaches the complete case
  // record set to the same reply.
  async investigate(
    caseId: string,
    query: string,
    history: any[] = [],
    detailLevel: 'standard' | 'full' = 'standard'
  ) {
    const res = await fetch(`${API_BASE}/ai/investigate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: caseId, query, history, detail_level: detailLevel })
    });
    return res.json();
  },
  async getFullBrief(caseId: string) {
    const res = await fetch(`${API_BASE}/ai/full-brief?case_id=${encodeURIComponent(caseId)}`);
    return res.json();
  },
  async getEntityDossier(caseId: string, entityId: string) {
    const res = await fetch(
      `${API_BASE}/ai/entity-dossier?case_id=${encodeURIComponent(caseId)}&entity_id=${encodeURIComponent(entityId)}`
    );
    return res.json();
  },
  async getHypotheses(caseId: string) {
    const res = await fetch(`${API_BASE}/ai/hypotheses?case_id=${encodeURIComponent(caseId)}`);
    return res.json();
  },

  // Cross-Case Intelligence Engine
  async getCrossCaseAnalysis(caseId: string, minConfidence = 0, bases: string[] = []) {
    const params = new URLSearchParams({ case_id: caseId });
    if (minConfidence > 0) params.append('min_confidence', String(minConfidence));
    bases.forEach(b => params.append('basis', b));
    const res = await fetch(`${API_BASE}/cross-case/analyse?${params.toString()}`);
    return res.json();
  },
  async getCrossCaseLink(caseId: string, linkId: string) {
    const res = await fetch(
      `${API_BASE}/cross-case/link/${encodeURIComponent(linkId)}?case_id=${encodeURIComponent(caseId)}`
    );
    return res.json();
  },
  async getCrossCaseBases() {
    const res = await fetch(`${API_BASE}/cross-case/bases`);
    return res.json();
  },

  // Controlled OSINT
  async expandOSINT(caseId: string, entityId: string, entityName: string, entityType: string) {
    const res = await fetch(`${API_BASE}/osint/expand`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: caseId, entity_id: entityId, entity_name: entityName, entity_type: entityType })
    });
    return res.json();
  },

  // Ingestion
  async reseedData() {
    const res = await fetch(`${API_BASE}/ingestion/reseed`, { method: 'POST' });
    return res.json();
  }
};
