/**
 * Re-export from the new location for backward compatibility
 * 
 * ChartTabView and other components import from @/stores/dataWorkspaceStore
 * but the actual store is now at @/features/canvas/data-workspace/stores/dataWorkspaceStore
 */
export * from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
export { useDataWorkspaceStore as default } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';

