import React from 'react';
import { Loader2, Shield } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { LoginScreen } from './LoginScreen';

/**
 * Nothing inside the application renders until a session exists. The backend
 * enforces this independently on every route; this only keeps the UI from
 * flashing panels it cannot fill.
 */
export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <div className="min-h-screen w-screen bg-dark-900 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <div className="flex items-center space-x-2 text-gray-500 text-xs">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>Restoring session…</span>
        </div>
      </div>
    );
  }

  if (status === 'unauthenticated') {
    return <LoginScreen />;
  }

  return <>{children}</>;
};
