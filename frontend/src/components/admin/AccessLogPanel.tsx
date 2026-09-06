import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Mail,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldCheck,
} from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import type { AccessLogEntry, AlertConfig, NotificationLogEntry } from '../../types';

/** Actions that read as a security concern rather than routine activity. */
const CONCERNING = new Set([
  'LOGIN_FAILED',
  'LOGIN_REJECTED',
  'LOGIN_THROTTLED',
  'PASSWORD_CHANGE_FAILED',
]);

const WINDOWS = [
  { label: '1h', hours: 1 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 24 * 7 },
  { label: '30d', hours: 24 * 30 },
];

export const AccessLogPanel: React.FC = () => {
  const [entries, setEntries] = useState<AccessLogEntry[]>([]);
  const [notifications, setNotifications] = useState<NotificationLogEntry[]>([]);
  const [config, setConfig] = useState<AlertConfig | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);

  const [windowHours, setWindowHours] = useState(24);
  const [view, setView] = useState<'access' | 'alerts'>('access');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [log, notif, cfg, sum] = await Promise.all([
        api.getAccessLog({ limit: 300, sinceHours: windowHours }),
        api.getNotificationLog(150),
        api.getAlertConfig(),
        api.getAccessSummary(windowHours),
      ]);
      setEntries(log);
      setNotifications(notif);
      setConfig(cfg);
      setSummary(sum);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the access record.');
    } finally {
      setIsLoading(false);
    }
  }, [windowHours]);

  useEffect(() => {
    void load();
  }, [load]);

  // The record is only useful if it is current; refresh while the tab is open.
  useEffect(() => {
    const timer = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const handleTestAlert = async () => {
    setIsTesting(true);
    try {
      const result = await api.sendTestAlert('both');
      const detail = result.outcomes
        .map(o => `${o.channel} ${o.status.toLowerCase()}`)
        .join(', ');
      setNotice(
        result.sent
          ? `Test alert sent — ${detail}.`
          : `Nothing delivered — ${detail}. ${result.hint ?? ''}`
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The test alert failed.');
    } finally {
      setIsTesting(false);
      window.setTimeout(() => setNotice(null), 12_000);
    }
  };

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center space-x-3">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <div>
            <h2 className="text-sm font-bold text-white">Access Record</h2>
            <p className="text-[10px] text-gray-500">
              Every sign-in, sign-out and account change on this platform.
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center bg-dark-900 border border-gray-700 rounded-md p-0.5">
            {WINDOWS.map(w => (
              <button
                key={w.hours}
                onClick={() => setWindowHours(w.hours)}
                className={`px-2 py-1 rounded text-[10px] font-semibold transition-colors ${
                  windowHours === w.hours
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleTestAlert}
            disabled={isTesting}
            title="Send a test alert to the Crime Branch head"
            className="flex items-center space-x-1.5 text-xs bg-dark-900 hover:bg-gray-800 border border-gray-700 text-amber-300 px-2.5 py-1.5 rounded-md transition-colors disabled:opacity-50"
          >
            <Send className={`w-3.5 h-3.5 ${isTesting ? 'animate-pulse' : ''}`} />
            <span className="hidden xl:inline">Test alert</span>
          </button>
          <button
            onClick={() => void load()}
            className="p-1.5 rounded-md bg-dark-900 border border-gray-700 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {(error || notice) && (
        <div
          className={`px-4 py-2 text-xs flex items-start space-x-2 flex-shrink-0 border-b ${
            error
              ? 'bg-red-500/10 text-red-300 border-red-500/20'
              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
          }`}
        >
          {error ? (
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          )}
          <span className="leading-relaxed">{error ?? notice}</span>
        </div>
      )}

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Where alerts are going, and whether the transports are live */}
        {config && (
          <div className="grid grid-cols-2 gap-3">
            <TransportCard
              icon={<Mail className="w-3.5 h-3.5" />}
              title="Email"
              live={config.email.configured}
              detail={config.email.host ?? 'no SMTP host configured'}
              scope={config.email.events === '*' ? 'every access event' : config.email.events}
            />
            <TransportCard
              icon={<MessageSquare className="w-3.5 h-3.5" />}
              title="SMS"
              live={config.sms.configured}
              detail={
                config.sms.provider === 'console'
                  ? 'provider is "console" — logged, not sent'
                  : `${config.sms.provider}${config.sms.from ? ` from ${config.sms.from}` : ''}`
              }
              scope={config.sms.events === '*' ? 'every access event' : 'high-severity events'}
            />
          </div>
        )}

        {config && (
          <div className="border border-gray-800 rounded-lg p-3 bg-dark-800/40">
            <div className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-2">
              Alerts go to
            </div>
            {config.recipients.length > 0 ? (
              config.recipients.map(r => (
                <div key={r.username} className="flex items-center justify-between text-[11px] py-0.5">
                  <span className="text-gray-300">
                    {r.full_name} <span className="text-gray-600 font-mono">({r.username})</span>
                  </span>
                  <span className="font-mono text-gray-500">
                    {r.email}
                    {r.phone_number ? ` · ${r.phone_number}` : ' · no phone number'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-[11px] text-amber-400">
                Nobody holds the CRIME_BRANCH_HEAD role
                {config.fallback_email ? ` — falling back to ${config.fallback_email}` : ''}.
              </p>
            )}
          </div>
        )}

        {summary && (
          <div className="grid grid-cols-5 gap-2">
            <Stat label="Events" value={summary.total_events} />
            <Stat label="Sign-ins" value={summary.successful_logins} />
            <Stat label="Failures" value={summary.failed_logins} tone={summary.failed_logins > 0 ? 'amber' : undefined} />
            <Stat label="People" value={summary.distinct_users} />
            <Stat label="IPs" value={summary.distinct_ips} />
          </div>
        )}

        <div className="flex items-center space-x-1 bg-dark-800/80 p-1 rounded-lg border border-gray-800 w-fit">
          {(['access', 'alerts'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1 rounded text-[11px] font-semibold transition-colors ${
                view === v ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {v === 'access' ? `Access log (${entries.length})` : `Alerts sent (${notifications.length})`}
            </button>
          ))}
        </div>

        {view === 'access' ? (
          <Table headers={['When', 'User', 'Action', 'IP address', 'Detail']}>
            {entries.length === 0 && <Empty colSpan={5} text="No access events in this window." />}
            {entries.map(e => (
              <tr key={e.id} className="hover:bg-dark-800/40">
                <Td mono muted>{new Date(e.created_at).toLocaleString()}</Td>
                <Td mono>{e.username}</Td>
                <Td>
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold border ${
                      CONCERNING.has(e.action)
                        ? 'bg-red-500/20 text-red-300 border-red-500/30'
                        : 'bg-gray-700/40 text-gray-300 border-gray-600/40'
                    }`}
                  >
                    {e.action}
                  </span>
                </Td>
                <Td mono muted>{e.ip_address ?? '—'}</Td>
                <Td muted>{formatDetails(e.details)}</Td>
              </tr>
            ))}
          </Table>
        ) : (
          <Table headers={['When', 'Event', 'Channel', 'Recipient', 'Result']}>
            {notifications.length === 0 && <Empty colSpan={5} text="No alerts dispatched yet." />}
            {notifications.map(n => (
              <tr key={n.id} className="hover:bg-dark-800/40">
                <Td mono muted>{new Date(n.created_at).toLocaleString()}</Td>
                <Td>
                  <span className="text-gray-300">{n.event_type}</span>
                  {n.severity === 'HIGH' && (
                    <span className="ml-1.5 text-[9px] text-amber-400 font-bold">HIGH</span>
                  )}
                </Td>
                <Td mono muted>{n.channel}</Td>
                <Td mono muted>{n.recipient}</Td>
                <Td>
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold border ${
                      n.status === 'SENT'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : n.status === 'FAILED'
                          ? 'bg-red-500/20 text-red-300 border-red-500/30'
                          : 'bg-gray-700/40 text-gray-400 border-gray-600/40'
                    }`}
                    title={n.error ?? undefined}
                  >
                    {n.status}
                  </span>
                  {n.error && (
                    <div className="text-[9px] text-gray-600 mt-0.5 truncate max-w-[22rem]">
                      {n.error}
                    </div>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </div>
    </div>
  );
};

/** Details carry nested objects (e.g. the changed fields of an account edit),
 *  which String() would flatten to "[object Object]". */
function formatDetails(details: Record<string, unknown> | undefined): string {
  const entries = Object.entries(details ?? {});
  if (entries.length === 0) return '—';
  return entries
    .map(([k, v]) => {
      if (v === null || v === undefined) return `${k}=—`;
      if (Array.isArray(v)) return `${k}=${v.join(',')}`;
      if (typeof v === 'object') {
        const inner = Object.entries(v as Record<string, unknown>)
          .map(([ik, iv]) => `${ik}:${String(iv)}`)
          .join(', ');
        return `${k}={${inner}}`;
      }
      return `${k}=${String(v)}`;
    })
    .join(' · ');
}

const TransportCard: React.FC<{
  icon: React.ReactNode;
  title: string;
  live: boolean;
  detail: string;
  scope: string;
}> = ({ icon, title, live, detail, scope }) => (
  <div
    className={`border rounded-lg p-3 ${
      live ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'
    }`}
  >
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center space-x-1.5 text-gray-300">
        {icon}
        <span className="text-xs font-bold">{title}</span>
      </div>
      <span
        className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold uppercase border ${
          live
            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
            : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
        }`}
      >
        {live ? 'Live' : 'Not sending'}
      </span>
    </div>
    <div className="text-[10px] text-gray-500 font-mono truncate">{detail}</div>
    <div className="text-[10px] text-gray-600 mt-0.5">Covers: {scope}</div>
  </div>
);

const Stat: React.FC<{ label: string; value: number; tone?: 'amber' }> = ({ label, value, tone }) => (
  <div className="border border-gray-800 rounded-lg p-2.5 bg-dark-800/40">
    <div className={`text-lg font-bold ${tone === 'amber' ? 'text-amber-400' : 'text-white'}`}>
      {value ?? 0}
    </div>
    <div className="text-[9px] uppercase tracking-wider text-gray-500">{label}</div>
  </div>
);

const Table: React.FC<{ headers: string[]; children: React.ReactNode }> = ({ headers, children }) => (
  <div className="border border-gray-800 rounded-lg overflow-x-auto">
    <table className="w-full text-xs">
      <thead className="bg-dark-800/80 text-gray-500">
        <tr className="text-left">
          {headers.map(h => (
            <th key={h} className="px-3 py-2 font-semibold whitespace-nowrap">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-800">{children}</tbody>
    </table>
  </div>
);

const Td: React.FC<{ children: React.ReactNode; mono?: boolean; muted?: boolean }> = ({
  children,
  mono,
  muted,
}) => (
  <td
    className={`px-3 py-2 align-top ${mono ? 'font-mono' : ''} ${
      muted ? 'text-gray-500' : 'text-gray-300'
    } ${mono ? 'text-[10px]' : ''}`}
  >
    {children}
  </td>
);

const Empty: React.FC<{ colSpan: number; text: string }> = ({ colSpan, text }) => (
  <tr>
    <td colSpan={colSpan} className="px-3 py-6 text-center text-gray-600">
      {text}
    </td>
  </tr>
);
