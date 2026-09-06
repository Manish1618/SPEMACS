import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  Loader2,
  Lock,
  RefreshCw,
  ShieldOff,
  UserPlus,
  Users,
} from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import { USER_ROLES } from '../../types';
import type { Case, ManagedUser, UserRole } from '../../types';

interface UserAdminPanelProps {
  cases: Case[];
  activeCaseId: string;
  onTeamChanged: () => void;
}

const BLANK_DRAFT = {
  username: '',
  email: '',
  full_name: '',
  role: 'INVESTIGATOR' as UserRole,
  badge_number: '',
  phone_number: '',
  password: '',
};

export const UserAdminPanel: React.FC<UserAdminPanelProps> = ({
  cases,
  activeCaseId,
  onTeamChanged,
}) => {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState({ ...BLANK_DRAFT });
  const [isCreating, setIsCreating] = useState(false);

  const [teamCaseId, setTeamCaseId] = useState(activeCaseId);
  const [isSavingTeam, setIsSavingTeam] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      setUsers(await api.listUsers());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the user list.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setTeamCaseId(activeCaseId);
  }, [activeCaseId]);

  const teamCase = useMemo(
    () => cases.find(c => c.case_id === teamCaseId),
    [cases, teamCaseId]
  );

  const report = (message: string) => {
    setNotice(message);
    setError(null);
    window.setTimeout(() => setNotice(null), 5000);
  };

  const run = async (userId: string, action: () => Promise<unknown>, message: string) => {
    setBusyId(userId);
    try {
      await action();
      await load();
      report(message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await api.createUser({
        username: draft.username.trim(),
        email: draft.email.trim(),
        full_name: draft.full_name.trim(),
        role: draft.role,
        badge_number: draft.badge_number.trim() || undefined,
        phone_number: draft.phone_number.trim() || undefined,
        password: draft.password,
      });
      setDraft({ ...BLANK_DRAFT });
      setShowCreate(false);
      await load();
      report('Account created. Assign them to a case below to grant access.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the account.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleResetPassword = (user: ManagedUser) => {
    const next = window.prompt(
      `New password for ${user.username}. Their sessions will be ended immediately.`
    );
    if (!next) return;
    void run(
      user.id,
      () => api.resetUserPassword(user.id, next),
      `Password reset for ${user.username}.`
    );
  };

  const toggleTeamMember = async (username: string) => {
    if (!teamCase) return;
    const current = teamCase.assigned_team || [];
    const next = current.includes(username)
      ? current.filter(name => name !== username)
      : [...current, username];

    setIsSavingTeam(true);
    try {
      await api.updateCaseTeam(teamCase.case_id, next);
      onTeamChanged();
      await load();
      report(`Case team for ${teamCase.case_id} updated.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update the case team.');
    } finally {
      setIsSavingTeam(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
      <div className="p-4 border-b border-gray-800 bg-dark-800/80 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center space-x-3">
          <Users className="w-4 h-4 text-indigo-400" />
          <div>
            <h2 className="text-sm font-bold text-white">Access Control</h2>
            <p className="text-[10px] text-gray-500">
              Accounts are created here only. There is no self-registration.
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => void load()}
            title="Reload"
            className="p-1.5 rounded-md bg-dark-900 border border-gray-700 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowCreate(v => !v)}
            className="flex items-center space-x-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-md font-semibold transition-colors"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>New investigator</span>
          </button>
        </div>
      </div>

      {(error || notice) && (
        <div
          className={`px-4 py-2 text-xs flex items-center space-x-2 flex-shrink-0 border-b ${
            error
              ? 'bg-red-500/10 text-red-300 border-red-500/20'
              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
          }`}
        >
          {error ? (
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
          )}
          <span>{error ?? notice}</span>
        </div>
      )}

      <div className="flex-1 overflow-auto p-4 space-y-5">
        {showCreate && (
          <form
            onSubmit={handleCreate}
            className="bg-dark-800/60 border border-gray-800 rounded-lg p-4 grid grid-cols-2 gap-3"
          >
            <Field label="Username">
              <input
                required
                value={draft.username}
                onChange={e => setDraft({ ...draft, username: e.target.value })}
                pattern="[a-zA-Z0-9_.\-]+"
                className={inputClass}
                placeholder="a_sharma"
              />
            </Field>
            <Field label="Email">
              <input
                required
                type="email"
                value={draft.email}
                onChange={e => setDraft({ ...draft, email: e.target.value })}
                className={inputClass}
                placeholder="a.sharma@spemass.example"
              />
            </Field>
            <Field label="Full name">
              <input
                required
                value={draft.full_name}
                onChange={e => setDraft({ ...draft, full_name: e.target.value })}
                className={inputClass}
                placeholder="Inspector A. Sharma"
              />
            </Field>
            <Field label="Badge number">
              <input
                value={draft.badge_number}
                onChange={e => setDraft({ ...draft, badge_number: e.target.value })}
                className={inputClass}
                placeholder="Optional"
              />
            </Field>
            <Field label="Phone (for SMS alerts)">
              <input
                value={draft.phone_number}
                onChange={e => setDraft({ ...draft, phone_number: e.target.value })}
                className={inputClass}
                placeholder="+919876543210"
              />
            </Field>
            <Field label="Role">
              <select
                value={draft.role}
                onChange={e => setDraft({ ...draft, role: e.target.value as UserRole })}
                className={inputClass}
              >
                {USER_ROLES.map(role => (
                  <option key={role} value={role}>
                    {role.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Initial password">
              <input
                required
                type="password"
                value={draft.password}
                onChange={e => setDraft({ ...draft, password: e.target.value })}
                className={inputClass}
                placeholder="At least 12 characters"
              />
            </Field>
            <div className="col-span-2 flex items-center justify-end space-x-2 pt-1">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="text-xs text-gray-400 hover:text-gray-200 px-3 py-1.5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating}
                className="flex items-center space-x-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-600 text-white px-3 py-1.5 rounded-md font-semibold transition-colors"
              >
                {isCreating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Create account</span>
              </button>
            </div>
          </form>
        )}

        {/* Accounts */}
        <div className="border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-dark-800/80 text-gray-500">
              <tr className="text-left">
                <th className="px-3 py-2 font-semibold">Investigator</th>
                <th className="px-3 py-2 font-semibold">Role</th>
                <th className="px-3 py-2 font-semibold">Cases</th>
                <th className="px-3 py-2 font-semibold">Last sign-in</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading && users.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-gray-600">
                    Loading accounts…
                  </td>
                </tr>
              )}
              {users.map(user => (
                <tr key={user.id} className="hover:bg-dark-800/40">
                  <td className="px-3 py-2">
                    <div className="text-gray-200 font-medium">{user.full_name}</div>
                    <div className="text-[10px] text-gray-600 font-mono">
                      {user.username}
                      {user.badge_number ? ` · ${user.badge_number}` : ''}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={user.role}
                      disabled={busyId === user.id}
                      onChange={e =>
                        void run(
                          user.id,
                          () => api.updateUser(user.id, { role: e.target.value }),
                          `${user.username} is now ${e.target.value.replaceAll('_', ' ')}.`
                        )
                      }
                      className="bg-dark-900 border border-gray-700 rounded px-1.5 py-1 text-[10px] text-gray-300 focus:outline-none focus:border-indigo-500"
                    >
                      {USER_ROLES.map(role => (
                        <option key={role} value={role}>
                          {role.replaceAll('_', ' ')}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2 text-gray-400 font-mono text-[10px]">
                    {user.role === 'ADMIN'
                      ? 'all'
                      : user.accessible_cases.length || '—'}
                  </td>
                  <td className="px-3 py-2 text-gray-500 text-[10px]">
                    {user.last_login_at
                      ? new Date(user.last_login_at).toLocaleString()
                      : 'never'}
                  </td>
                  <td className="px-3 py-2">
                    {!user.is_active ? (
                      <Badge tone="red">Deactivated</Badge>
                    ) : user.is_locked ? (
                      <Badge tone="amber">Locked</Badge>
                    ) : (
                      <Badge tone="emerald">Active</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end space-x-1">
                      {user.is_locked && (
                        <IconButton
                          title="Unlock account"
                          onClick={() =>
                            void run(
                              user.id,
                              () => api.updateUser(user.id, { unlock: true }),
                              `${user.username} unlocked.`
                            )
                          }
                        >
                          <Lock className="w-3.5 h-3.5 text-amber-400" />
                        </IconButton>
                      )}
                      <IconButton
                        title="Reset password"
                        onClick={() => handleResetPassword(user)}
                      >
                        <KeyRound className="w-3.5 h-3.5 text-indigo-300" />
                      </IconButton>
                      <IconButton
                        title={user.is_active ? 'Deactivate account' : 'Reactivate account'}
                        onClick={() =>
                          void run(
                            user.id,
                            () => api.updateUser(user.id, { is_active: !user.is_active }),
                            user.is_active
                              ? `${user.username} deactivated and signed out everywhere.`
                              : `${user.username} reactivated.`
                          )
                        }
                      >
                        <ShieldOff
                          className={`w-3.5 h-3.5 ${
                            user.is_active ? 'text-red-400' : 'text-emerald-400'
                          }`}
                        />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Case team membership - the control that actually grants case access */}
        <div className="border border-gray-800 rounded-lg p-4 bg-dark-800/40">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-white">Case team</h3>
              <p className="text-[10px] text-gray-500">
                Only the lead investigator and the named team can open a case.
              </p>
            </div>
            <select
              value={teamCaseId}
              onChange={e => setTeamCaseId(e.target.value)}
              className="bg-dark-900 border border-gray-700 rounded-md px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
            >
              {cases.map(c => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id}
                </option>
              ))}
            </select>
          </div>

          {teamCase ? (
            <div className="grid grid-cols-2 gap-2">
              {users
                .filter(u => u.is_active && u.role !== 'ADMIN')
                .map(user => {
                  const isLead = teamCase.lead_investigator === user.username;
                  const isMember = isLead || (teamCase.assigned_team || []).includes(user.username);
                  return (
                    <label
                      key={user.id}
                      className={`flex items-center space-x-2 px-2.5 py-1.5 rounded-md border text-[11px] cursor-pointer transition-colors ${
                        isMember
                          ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-200'
                          : 'bg-dark-900 border-gray-800 text-gray-400 hover:border-gray-700'
                      } ${isLead || isSavingTeam ? 'cursor-not-allowed opacity-80' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={isMember}
                        disabled={isLead || isSavingTeam}
                        onChange={() => void toggleTeamMember(user.username)}
                        className="accent-indigo-500"
                      />
                      <span className="font-mono">{user.username}</span>
                      {isLead && (
                        <span className="text-[9px] text-amber-400 font-bold uppercase">
                          lead
                        </span>
                      )}
                    </label>
                  );
                })}
            </div>
          ) : (
            <p className="text-[11px] text-gray-600">Select a case.</p>
          )}
        </div>
      </div>
    </div>
  );
};

const inputClass =
  'w-full bg-dark-900 border border-gray-700 rounded-md px-2.5 py-1.5 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500';

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="space-y-1">
    <label className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
      {label}
    </label>
    {children}
  </div>
);

const Badge: React.FC<{ tone: 'red' | 'amber' | 'emerald'; children: React.ReactNode }> = ({
  tone,
  children,
}) => {
  const tones = {
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  };
  return (
    <span
      className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold uppercase border ${tones[tone]}`}
    >
      {children}
    </span>
  );
};

const IconButton: React.FC<{
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}> = ({ title, onClick, children }) => (
  <button
    type="button"
    title={title}
    onClick={onClick}
    className="p-1.5 rounded hover:bg-gray-800 transition-colors"
  >
    {children}
  </button>
);
