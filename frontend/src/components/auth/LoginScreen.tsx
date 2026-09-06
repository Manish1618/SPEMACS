import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, Lock, Shield, User as UserIcon } from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import type { AuthConfig } from '../../types';

export const LoginScreen: React.FC = () => {
  const { login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLocked, setIsLocked] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [config, setConfig] = useState<AuthConfig | null>(null);

  // Demo credentials are served only while the backend runs in demo mode, so a
  // production deployment renders nothing here.
  useEffect(() => {
    let cancelled = false;
    api
      .authConfig()
      .then(c => {
        if (!cancelled) setConfig(c);
      })
      .catch(() => {
        /* the login form works regardless */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    setIsLocked(false);

    try {
      await login(username.trim(), password);
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setIsLocked(apiError?.status === 423);
      setError(
        apiError?.message ??
          'Could not reach the SPEMASS server. Check that the API is running.'
      );
      setPassword('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillDemo = (demoUser: string, demoPass: string) => {
    setUsername(demoUser);
    setPassword(demoPass);
    setError(null);
    setIsLocked(false);
  };

  return (
    <div className="min-h-screen w-screen bg-dark-900 text-gray-100 flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-lg shadow-indigo-500/20 mb-4">
            <Shield className="w-7 h-7 text-white" />
          </div>
          <h1 className="font-bold text-2xl tracking-wider text-white">SPEMASS</h1>
          <p className="text-[11px] text-gray-500 mt-1.5 text-center leading-relaxed">
            Secure Pattern &amp; Evidence Mapping and Analysis of Suspicious Structures
          </p>
          <span className="mt-3 text-[9px] bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider border border-amber-500/30">
            Restricted — Authorised Investigators Only
          </span>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-dark-800/80 border border-gray-800 rounded-xl p-6 shadow-2xl space-y-4"
        >
          <div className="space-y-1.5">
            <label
              htmlFor="username"
              className="text-[10px] font-bold uppercase tracking-wider text-gray-400"
            >
              Username
            </label>
            <div className="relative">
              <UserIcon className="w-4 h-4 text-gray-600 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-dark-900 border border-gray-700 rounded-md pl-9 pr-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors"
                placeholder="rajiv_sen"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="password"
              className="text-[10px] font-bold uppercase tracking-wider text-gray-400"
            >
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-gray-600 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyUp={e => setCapsLock(e.getModifierState?.('CapsLock') ?? false)}
                className="w-full bg-dark-900 border border-gray-700 rounded-md pl-9 pr-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors"
                placeholder="••••••••"
              />
            </div>
            {capsLock && (
              <p className="text-[10px] text-amber-400 pt-0.5">Caps Lock is on.</p>
            )}
          </div>

          {error && (
            <div
              role="alert"
              className={`flex items-start space-x-2 text-xs rounded-md px-3 py-2 border ${
                isLocked
                  ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                  : 'bg-red-500/10 text-red-300 border-red-500/30'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || !username.trim() || !password}
            className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-white text-sm font-semibold py-2 rounded-md transition-colors"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isSubmitting ? 'Verifying…' : 'Sign in'}</span>
          </button>

          <p className="text-[10px] text-gray-600 text-center leading-relaxed pt-1">
            Every sign-in attempt is recorded in the audit log. Accounts lock after
            repeated failures.
          </p>
        </form>

        {config?.demo_mode && config.demo_credentials.length > 0 && (
          <div className="mt-5 bg-dark-800/50 border border-gray-800 rounded-lg p-3">
            <div className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-2">
              Demo mode — synthetic accounts
            </div>
            <div className="space-y-1">
              {config.demo_credentials.map(cred => (
                <button
                  key={cred.username}
                  type="button"
                  onClick={() => fillDemo(cred.username, cred.password)}
                  className="w-full flex items-center justify-between text-[10px] px-2 py-1.5 rounded hover:bg-gray-800/60 transition-colors text-left"
                >
                  <span className="font-mono text-gray-300">{cred.username}</span>
                  <span className="text-gray-600 font-mono">{cred.role}</span>
                </button>
              ))}
            </div>
            <p className="text-[9px] text-gray-600 mt-2 leading-relaxed">
              These exist only because the API is running with DEMO_MODE on.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
