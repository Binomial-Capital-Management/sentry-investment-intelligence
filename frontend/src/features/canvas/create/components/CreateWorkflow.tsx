/**
 * CreateWorkflow - Routes directly to the unified workspace.
 *
 * /canvas → Unified workspace (tabs auto-persist individually)
 */

import { useNavigate } from 'react-router-dom';
import { DataWorkspace } from '@/features/canvas/data-workspace';
import { useDataWorkspaceStore } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';

export function CreateWorkflow() {
  const navigate = useNavigate();

  const handleBack = () => {
    useDataWorkspaceStore.getState().resetWorkspace();
    navigate('/canvas', { replace: true });
  };

  return (
    <DataWorkspace
      onBack={handleBack}
    />
  );
}
