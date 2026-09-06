/**
 * The access token, held in memory for the lifetime of the page and nowhere else.
 *
 * Deliberately not localStorage or sessionStorage: anything readable from
 * JavaScript is readable by an XSS payload. The durable half of the session is
 * the httpOnly refresh cookie, which script cannot read at all, so a reload
 * restores the session by calling /auth/refresh rather than by reading a token
 * back out of storage.
 */

let accessToken: string | null = null;
let expiresAt = 0;

type Listener = () => void;
const listeners = new Set<Listener>();

/** Renew a little before expiry so a request never races the deadline. */
const RENEW_AT = 0.8;

let renewTimer: ReturnType<typeof setTimeout> | null = null;
let onRenew: (() => void) | null = null;

export const authStore = {
  get(): string | null {
    return accessToken;
  },

  set(token: string, expiresInMinutes: number): void {
    accessToken = token;
    expiresAt = Date.now() + expiresInMinutes * 60_000;
    this.scheduleRenewal(expiresInMinutes);
    notify();
  },

  clear(): void {
    accessToken = null;
    expiresAt = 0;
    if (renewTimer) {
      clearTimeout(renewTimer);
      renewTimer = null;
    }
    notify();
  },

  isExpired(): boolean {
    return !accessToken || Date.now() >= expiresAt;
  },

  /** Registers the callback the silent-refresh timer fires. */
  setRenewHandler(handler: (() => void) | null): void {
    onRenew = handler;
  },

  scheduleRenewal(expiresInMinutes: number): void {
    if (renewTimer) clearTimeout(renewTimer);
    const delay = Math.max(expiresInMinutes * 60_000 * RENEW_AT, 30_000);
    renewTimer = setTimeout(() => onRenew?.(), delay);
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

function notify(): void {
  listeners.forEach(listener => listener());
}

/**
 * The CSRF token the server set alongside the refresh cookie. Readable on
 * purpose - it is echoed back in a header so the server can distinguish a
 * same-origin request from a cross-site one.
 */
export function readCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)spemass_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

/** True when a refresh is even worth attempting. */
export function hasSessionCookie(): boolean {
  return readCsrfToken() !== '';
}
