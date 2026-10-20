import { Routes, Route, useNavigate, Navigate, useParams } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout/Layout';
import ChatInterface from './components/Chat/ChatInterface';
import Landing from './components/Landing/Landing';
import Pricing from './components/Landing/Pricing';
import About from './components/About/About';
import Contact from './components/Contact/Contact';
import Capabilities from './components/Capabilities/Capabilities';
import Performance from './components/Performance/Performance';
import RootRoute from './components/Routes/RootRoute';

// Auth feature module (new architecture)
import { LoginPage, RegisterPage, SSOCallbackPage, AuthGate } from './features/auth';
import PortfolioPage from './components/Portfolio/PortfolioPage';
import PortfolioDetailPage from './components/Portfolio/PortfolioDetailPage';
import PortfolioTransactionsPage from './components/Portfolio/PortfolioTransactionsPage';
import PostMortemDetailPage from './components/TaskTracker/PostMortems/PostMortemDetailPage';
import { MarketplacePage } from './pages/Marketplace/MarketplacePage';
import { IntegrationDetail } from './pages/Marketplace/IntegrationDetail';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import OrganizationSettings from './components/Settings/OrganizationSettings';
import Workflows from './pages/Workflows';
import Tasks from './pages/Tasks';
import TaskBuilder from './components/Task/TaskBuilder';
import Calendar from './pages/Calendar';
import Markets from './pages/Markets';
import { MarketLists } from './pages/MarketLists';
import { Events } from './pages/Events';
import { CompanyDetail } from './pages/CompanyDetail';
import ComponentDemo from './components/Common/ComponentDemo';
import { CreateWorkflow } from '@/features/canvas/create';

// Redirect component for legacy process viewer route
function ProcessRedirect() {
  const { processId } = useParams<{ processId: string }>();
  return <Navigate to={`/canvas?mode=tool&workspace=${processId}`} replace />;
}
import PublicChatDemo from './pages/PublicChatDemo';
import PublicWorkflowDemo from './pages/PublicWorkflowDemo';
import PublicDashboardDemo from './pages/PublicDashboardDemo';
import PublicTasksDemo from './pages/PublicTasksDemo';
import { Privacy, Terms } from './components/Legal';
import { useEffect } from 'react';
import { useUIStore } from '@stores/uiStore';
import { useWorkflowExecution } from '@stores/workflowExecutionStore';
import { useGlobalWorkflowManager } from '@hooks/useGlobalWorkflowManager';
import { getBackendVersion } from '@utils/version';
import ErrorBoundary from '@components/Common/ErrorBoundary';
import './styles/typography.css';
import './styles/global-responsive.css';

// Global minimized workflow indicator component
function GlobalMinimizedIndicator() {
  const { activeExecution, isMinimized, restore } = useWorkflowExecution();
  const navigate = useNavigate();

  if (!activeExecution || !isMinimized) return null;

  return (
    <>
      <style>
        {`
          @keyframes pulse {
            0%, 100% {
              box-shadow: 0 0 0 0 rgba(0, 120, 212, 0.4);
            }
            50% {
              box-shadow: 0 0 0 6px rgba(0, 120, 212, 0);
            }
          }
        `}
      </style>
      <div
        onClick={() => {
          restore();
          navigate('/workflows');
        }}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          background: 'white',
          border: '1px solid #E1DFDD',
          color: '#2C3E50',
          padding: '12px 20px',
          borderRadius: '6px',
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          zIndex: 10000, // Above everything else
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-2px)';
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.06)';
          e.currentTarget.style.borderColor = '#0078D4';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)';
          e.currentTarget.style.borderColor = '#E1DFDD';
        }}
      >
        {/* Status Indicator */}
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: activeExecution.status === 'running' ? '#0078D4' :
                     activeExecution.status === 'succeeded' ? '#10B981' :
                     activeExecution.status === 'failed' ? '#EF4444' : '#6B7280',
          boxShadow: activeExecution.status === 'running' ? '0 0 0 3px rgba(0, 120, 212, 0.2)' : 'none',
          animation: activeExecution.status === 'running' ? 'pulse 2s infinite' : 'none',
        }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <span style={{ fontSize: '13px', fontWeight: '600', color: '#2A2A2A' }}>
            {activeExecution.workflowName}
          </span>
          <span style={{
            fontSize: '11px',
            color: activeExecution.status === 'running' ? '#0078D4' :
                   activeExecution.status === 'succeeded' ? '#10B981' :
                   activeExecution.status === 'failed' ? '#EF4444' : '#6B7280',
            fontWeight: '500',
          }}>
            {activeExecution.status === 'running' && 'Running'}
            {activeExecution.status === 'succeeded' && 'Complete'}
            {activeExecution.status === 'failed' && 'Failed'}
          </span>
          <span style={{ fontSize: '10px', color: '#6B7280', opacity: 0.8 }}>
            Click to restore
          </span>
        </div>

        {/* Arrow Icon */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#6B7280"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ marginLeft: '4px' }}
        >
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </div>
    </>
  );
}

function App() {
  const { setBackendVersion } = useUIStore();

  // Initialize global workflow manager (polling + WebSocket)
  useGlobalWorkflowManager();

  useEffect(() => {
    getBackendVersion().then(setBackendVersion).catch(() => setBackendVersion('unknown'));
  }, [setBackendVersion]);

  return (
    <ErrorBoundary>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />

      {/* Global minimized workflow indicator - shows on ALL routes */}
      <GlobalMinimizedIndicator />

      <Routes>
        {/* Smart root - shows landing or dashboard based on auth */}
        <Route path="/" element={<RootRoute />} />

        {/* App routes - show with Layout wrapper */}
        <Route path="/" element={<AuthGate fallback="/"><Layout /></AuthGate>}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="chat" element={<ChatInterface />} />
          <Route path="workflows" element={<Workflows />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="review" element={<Calendar />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="portfolio/:id" element={<PortfolioDetailPage />} />
          <Route path="portfolio/:id/transactions" element={<PortfolioTransactionsPage />} />
          <Route path="postmortem/:id" element={<PostMortemDetailPage />} />
          <Route path="company/:ticker" element={<CompanyDetail />} />
          <Route path="canvas" element={<CreateWorkflow />} />
          <Route path="canvas/process/:processId" element={<ProcessRedirect />} />
          {/* <Route path="markets" element={<Markets />} /> */}
          <Route path="market-lists" element={<MarketLists />} />
          <Route path="events" element={<Events />} />
          <Route path="settings" element={<Settings />} />
          <Route path="settings/organization" element={<OrganizationSettings />} />
          <Route path="marketplace" element={<MarketplacePage />} />
          <Route path="marketplace/:id" element={<IntegrationDetail />} />
          <Route path="demo" element={<ComponentDemo />} />
        </Route>

        {/* Task Builder Routes - Outside Layout to be fullscreen */}
        <Route path="/tasks/new" element={<AuthGate fallback="/"><TaskBuilder /></AuthGate>} />
        <Route path="/tasks/:taskId" element={<AuthGate fallback="/"><TaskBuilder /></AuthGate>} />

        {/* Public pages */}
        <Route path="/about" element={<About />} />
        <Route path="/capabilities" element={<Capabilities />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/chat-demo" element={<PublicChatDemo />} />
        <Route path="/workflow-demo" element={<PublicWorkflowDemo />} />
        <Route path="/dashboard-demo" element={<PublicDashboardDemo />} />
        <Route path="/tasks-demo" element={<PublicTasksDemo />} />

        {/* Auth routes - using new feature module */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/sign-up" element={<RegisterPage />} />
        <Route path="/sso-callback" element={<SSOCallbackPage />} />

        {/* Legacy route redirect */}
        <Route path="/sentry" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;
