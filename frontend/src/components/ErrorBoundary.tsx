import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("SPEMASS React Uncaught Error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-screen bg-slate-950 text-white flex flex-col items-center justify-center p-8">
          <div className="max-w-2xl w-full bg-slate-900 border border-red-500/40 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-red-400">
              <span className="text-2xl font-bold">⚠️ SPEMASS Frontend Error Encountered</span>
            </div>
            <p className="text-sm text-gray-300">
              An unhandled exception occurred during component render. Diagnostic details below:
            </p>
            <div className="bg-black/80 rounded-lg p-4 font-mono text-xs text-red-300 overflow-x-auto max-h-60 border border-red-900/50">
              {this.state.error?.toString()}
              {this.state.errorInfo?.componentStack && (
                <div className="mt-2 text-gray-400">
                  {this.state.errorInfo.componentStack}
                </div>
              )}
            </div>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
