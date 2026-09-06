import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, ApiError, setSessionLostHandler } from '../lib/api';
import { authStore, hasSessionCookie } from '../lib/authStore';
import type { AuthUser } from '../types';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<string>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  const endSession = useCallback(() => {
    authStore.clear();
    setUser(null);
    setStatus('unauthenticated');
  }, []);

  // A 401 that survives a refresh attempt means the session is genuinely over.
  useEffect(() => {
    setSessionLostHandler(endSession);
    return () => setSessionLostHandler(null);
  }, [endSession]);

  // On load, try to rebuild the session from the httpOnly refresh cookie. The
  // access token itself was never persisted, so this is the only way back in.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!hasSessionCookie()) {
        if (!cancelled) setStatus('unauthenticated');
        return;
      }
      try {
        const result = await api.refresh();
        if (cancelled) return;
        authStore.set(result.access_token, result.expires_in_minutes);
        setUser(result.user);
        setStatus('authenticated');
      } catch {
        if (!cancelled) endSession();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [endSession]);

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.login(username, password);
    authStore.set(result.access_token, result.expires_in_minutes);
    setUser(result.user);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // The server-side session may already be gone; clearing locally is enough.
    }
    endSession();
  }, [endSession]);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const result = await api.changePassword(currentPassword, newPassword);
      // The server drops every session on a password change, so sign back in.
      endSession();
      return result.detail;
    },
    [endSession]
  );

  const refreshProfile = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) endSession();
    }
  }, [endSession]);

  return (
    <AuthContext.Provider
      value={{ user, status, login, logout, changePassword, refreshProfile }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside an AuthProvider');
  return ctx;
}
