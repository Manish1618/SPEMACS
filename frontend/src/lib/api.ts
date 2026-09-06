import { authStore, hasSessionCookie, readCsrfToken } from './authStore';
import type {
  AccessLogEntry,
  AlertConfig,
  AuthConfig,
  AuthUser,
  LoginResult,
  ManagedUser,
  NotificationLogEntry,
} from '../types';

// Same-origin by default, through the Vite proxy in vite.config.ts. Keeping the
// API on our own origin is what lets the refresh cookie stay SameSite=Strict.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1';

const CSRF_HEADER = 'X-CSRF-Token';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Called when the session is gone for good, so the UI can return to the login screen. */
let onSessionLost: (() => void) | null = null;
export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

// Concurrent 401s share one refresh attempt rather than each firing their own,
// which would rotate the cookie several times and trip reuse detection.
let refreshInFlight: Promise<boolean> | null = null;

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Sent as-is (FormData). Skips the JSON content type. */
  raw?: BodyInit;
  /** Internal: prevents a refresh attempt from recursing on its own 401. */
  skipRefresh?: boolean;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};

  const token = authStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  const csrf = readCsrfToken();
  if (csrf) headers[CSRF_HEADER] = csrf;

  let body: BodyInit | undefined;
  if (options.raw !== undefined) {
    body = options.raw;
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }

  return fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    credentials: 'include', // carries the httpOnly refresh cookie
  });
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const detail =
      (payload as { detail?: unknown } | null)?.detail ?? (typeof payload === 'string' ? payload : '');
    const message =
      typeof detail === 'string' && detail
        ? detail
        : `Request failed (${res.status} ${res.statusText}).`;
    throw new ApiError(res.status, message);
  }

  return payload as T;
}

/** Swap the refresh cookie for a new access token. Returns whether it worked. */
async function attemptRefresh(): Promise<boolean> {
  if (!hasSessionCookie()) return false;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await send('/auth/refresh', { method: 'POST', skipRefresh: true });
        if (!res.ok) return false;
        const data = (await res.json()) as LoginResult;
        authStore.set(data.access_token, data.expires_in_minutes ?? 15);
        return true;
      } catch {
        return false;
      } finally {
        // Cleared on the next tick so callers awaiting this promise all see it.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }

  return refreshInFlight;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await send(path, options);

  // One silent renewal, then replay. If that fails the session is over.
  if (res.status === 401 && !options.skipRefresh) {
    const renewed = await attemptRefresh();
    if (renewed) {
      res = await send(path, { ...options, skipRefresh: true });
    } else {
      authStore.clear();
      onSessionLost?.();
    }
  }

  return parse<T>(res);
}

// The silent-refresh timer in authStore renews before the token lapses, so a
// long-idle tab does not have to fail a request first.
authStore.setRenewHandler(() => {
  void attemptRefresh();
});

export const api = {
  // --- Authentication ---
  async authConfig(): Promise<AuthConfig> {
    return request<AuthConfig>('/auth/config');
  },
  async login(username: string, password: string): Promise<LoginResult> {
    return request<LoginResult>('/auth/login', {
      method: 'POST',
      body: { username, password },
      skipRefresh: true,
    });
  },
  async refresh(): Promise<LoginResult> {
    return request<LoginResult>('/auth/refresh', { method: 'POST', skipRefresh: true });
  },
  async logout(): Promise<void> {
    await request<{ detail: string }>('/auth/logout', { method: 'POST', skipRefresh: true });
  },
  async me(): Promise<AuthUser> {
    return request<AuthUser>('/auth/me');
  },
  async changePassword(currentPassword: string, newPassword: string) {
    return request<{ detail: string }>('/auth/change-password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    });
  },

  // --- User administration (ADMIN only) ---
  async listUsers(): Promise<ManagedUser[]> {
    return request<ManagedUser[]>('/users');
  },
  async createUser(payload: {
    username: string;
    email: string;
    full_name: string;
    role: string;
    badge_number?: string;
    phone_number?: string;
    password: string;
  }): Promise<ManagedUser> {
    return request<ManagedUser>('/users', { method: 'POST', body: payload });
  },
  async updateUser(
    userId: string,
    payload: Partial<{
      email: string;
      full_name: string;
      role: string;
      badge_number: string;
      phone_number: string;
      is_active: boolean;
      unlock: boolean;
    }>
  ): Promise<ManagedUser> {
    return request<ManagedUser>(`/users/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: payload,
    });
  },
  async resetUserPassword(userId: string, newPassword: string) {
    return request<{ detail: string }>(`/users/${encodeURIComponent(userId)}/reset-password`, {
      method: 'POST',
      body: { new_password: newPassword },
    });
  },
  async revokeUserSessions(userId: string) {
    return request<{ detail: string }>(`/users/${encodeURIComponent(userId)}/revoke-sessions`, {
      method: 'POST',
    });
  },

  // --- Access record & alerting (ADMIN and CRIME_BRANCH_HEAD) ---
  async getAccessLog(params: { limit?: number; username?: string; action?: string; sinceHours?: number } = {}) {
    const q = new URLSearchParams();
    if (params.limit) q.append('limit', String(params.limit));
    if (params.username) q.append('username', params.username);
    if (params.action) q.append('action', params.action);
    if (params.sinceHours) q.append('since_hours', String(params.sinceHours));
    const query = q.toString();
    return request<AccessLogEntry[]>(`/audit/access-log${query ? `?${query}` : ''}`);
  },
  async getAccessSummary(sinceHours = 24) {
    return request<Record<string, any>>(`/audit/access-log/summary?since_hours=${sinceHours}`);
  },
  async getNotificationLog(limit = 100) {
    return request<NotificationLogEntry[]>(`/audit/notifications?limit=${limit}`);
  },
  async getAlertConfig() {
    return request<AlertConfig>('/audit/alert-config');
  },
  async sendTestAlert(channel: 'both' | 'email' | 'sms' = 'both') {
    return request<{ sent: boolean; outcomes: { channel: string; recipient: string; status: string }[]; hint?: string | null }>(
      `/audit/test-alert?channel=${channel}`,
      { method: 'POST' }
    );
  },

  // Cases
  async getCases() {
    return request<any[]>('/cases');
  },
  async getCaseById(caseId: string) {
    return request<any>(`/cases/${encodeURIComponent(caseId)}`);
  },
  async updateCaseTeam(caseId: string, assignedTeam: string[]) {
    return request<any>(`/cases/${encodeURIComponent(caseId)}/team`, {
      method: 'PUT',
      body: { assigned_team: assignedTeam },
    });
  },

  // Graph
  async getGraph(caseId: string) {
    return request<any>(`/graph/case/${encodeURIComponent(caseId)}`);
  },
  async getKHop(entityId: string, k: number = 2) {
    return request<any>(`/graph/k-hop?entity_id=${encodeURIComponent(entityId)}&k=${k}`);
  },
  async getShortestPath(sourceId: string, targetId: string) {
    return request<any>(
      `/graph/shortest-path?source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targetId)}`
    );
  },
  async getGraphAnalytics(caseId?: string) {
    return request<any>(
      caseId ? `/graph/analytics?case_id=${encodeURIComponent(caseId)}` : '/graph/analytics'
    );
  },
  async getCrossCase() {
    return request<any>('/graph/cross-case');
  },
  async getAnomalies() {
    return request<any>('/graph/anomalies');
  },
  async mergeEntities(primaryId: string, duplicateId: string) {
    return request<any>(
      `/graph/merge-entities?primary_id=${encodeURIComponent(primaryId)}&duplicate_id=${encodeURIComponent(duplicateId)}`,
      { method: 'POST' }
    );
  },

  // Workspace: Map & Timeline
  async getMapEvents(caseId?: string, entityId?: string) {
    return request<any>(`/workspace/map-events${scopeQuery(caseId, entityId)}`);
  },
  async getTimeline(caseId?: string, entityId?: string) {
    return request<any>(`/workspace/timeline${scopeQuery(caseId, entityId)}`);
  },

  // Evidence & Custody
  async getEvidence(caseId?: string) {
    return request<any>(
      caseId ? `/evidence?case_id=${encodeURIComponent(caseId)}` : '/evidence'
    );
  },
  async getEvidenceDetail(evidenceId: string) {
    return request<any>(`/evidence/${encodeURIComponent(evidenceId)}`);
  },
  async verifyIntegrity(evidenceId: string) {
    return request<any>(`/evidence/${encodeURIComponent(evidenceId)}/verify`, { method: 'POST' });
  },
  async simulateTamper(evidenceId: string) {
    return request<any>(`/evidence/${encodeURIComponent(evidenceId)}/simulate-tamper`, {
      method: 'POST',
    });
  },
  async restoreClean(evidenceId: string) {
    return request<any>(`/evidence/${encodeURIComponent(evidenceId)}/restore-clean`, {
      method: 'POST',
    });
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
    return request<any>('/ai/investigate', {
      method: 'POST',
      body: { case_id: caseId, query, history, detail_level: detailLevel },
    });
  },
  async getFullBrief(caseId: string) {
    return request<any>(`/ai/full-brief?case_id=${encodeURIComponent(caseId)}`);
  },
  async getEntityDossier(caseId: string, entityId: string) {
    return request<any>(
      `/ai/entity-dossier?case_id=${encodeURIComponent(caseId)}&entity_id=${encodeURIComponent(entityId)}`
    );
  },
  async getHypotheses(caseId: string) {
    return request<any>(`/ai/hypotheses?case_id=${encodeURIComponent(caseId)}`);
  },

  // Cross-Case Intelligence Engine
  async getCrossCaseAnalysis(caseId: string, minConfidence = 0, bases: string[] = []) {
    const params = new URLSearchParams({ case_id: caseId });
    if (minConfidence > 0) params.append('min_confidence', String(minConfidence));
    bases.forEach(b => params.append('basis', b));
    return request<any>(`/cross-case/analyse?${params.toString()}`);
  },
  async getCrossCaseLink(caseId: string, linkId: string) {
    return request<any>(
      `/cross-case/link/${encodeURIComponent(linkId)}?case_id=${encodeURIComponent(caseId)}`
    );
  },
  async getCrossCaseBases() {
    return request<any>('/cross-case/bases');
  },

  // Controlled OSINT
  async expandOSINT(caseId: string, entityId: string, entityName: string, entityType: string) {
    return request<any>('/osint/expand', {
      method: 'POST',
      body: {
        case_id: caseId,
        entity_id: entityId,
        entity_name: entityName,
        entity_type: entityType,
      },
    });
  },

  // Ingestion
  async uploadDocument(caseId: string, title: string, fileType: string, file: File) {
    const formData = new FormData();
    formData.append('case_id', caseId);
    formData.append('title', title);
    formData.append('file_type', fileType);
    formData.append('file', file);
    return request<any>('/ingestion/upload', { method: 'POST', raw: formData });
  },
  async reseedData() {
    return request<any>('/ingestion/reseed', { method: 'POST' });
  },
};

function scopeQuery(caseId?: string, entityId?: string): string {
  const params = new URLSearchParams();
  if (caseId) params.append('case_id', caseId);
  if (entityId) params.append('entity_id', entityId);
  const query = params.toString();
  return query ? `?${query}` : '';
}
