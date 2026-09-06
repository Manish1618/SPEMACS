import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { AuthProvider } from './context/AuthContext.tsx'
import { AuthGate } from './components/auth/AuthGate.tsx'

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <AuthProvider>
      <AuthGate>
        <App />
      </AuthGate>
    </AuthProvider>
  </ErrorBoundary>,
)
