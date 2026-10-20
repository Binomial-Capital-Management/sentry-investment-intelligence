import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useUIStore } from '@stores/uiStore';
import { usePortfolioStore } from '@stores/portfolioStore';
import NavigationRail from '@components/navigation/NavigationRail/NavigationRail';
import SystemBar from './SystemBar';
import { GlobalSearch } from '@components/Common/SearchBar';
import { useKeyboardShortcuts } from '@hooks/useKeyboardShortcuts';
import { useCommandPalette } from '@hooks/useCommandPalette';
import CommandPalette from '@components/Common/CommandPalette';

const Layout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const commandPalette = useCommandPalette();
  useUIStore((state) => state.sidebarExpanded); // retain subscription if needed later
  const { loadPortfolios } = usePortfolioStore();

  // Hide rail + dev bar when inside canvas workspace
  const isCanvasWorkspaceView =
    location.pathname.startsWith('/canvas/process') ||
    location.pathname === '/canvas';

  // Setup keyboard shortcuts
  useKeyboardShortcuts({
    onSearch: () => commandPalette.open(),
    onNewChat: () => {
      // Navigate to chat page - chat component will handle thread creation
      navigate('/chat');
    },
    onEscape: () => {
      setIsSearchOpen(false);
      commandPalette.close();
    },
  });

  // Load portfolios on mount (but not threads - we start with a default thread)
  useEffect(() => {
    loadPortfolios();
  }, []);

  return (
    <>
      <div className="h-screen overflow-hidden flex" style={{ background: 'var(--bg-surface)' }}>
        <NavigationRail />

        <div className="flex-1 flex flex-col overflow-hidden">
          {!isCanvasWorkspaceView && <SystemBar />}

          <main className="flex-1 flex flex-col overflow-hidden">
            <Outlet />
          </main>
        </div>
      </div>

      {/* Global Search Modal */}
      <GlobalSearch isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />

      {/* Command Palette */}
      <CommandPalette
        isOpen={commandPalette.isOpen}
        onClose={commandPalette.close}
      />
    </>
  );
};

export default Layout;
