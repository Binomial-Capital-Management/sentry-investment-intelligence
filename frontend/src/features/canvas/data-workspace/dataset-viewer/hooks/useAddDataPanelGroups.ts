import { useState, useCallback, useMemo } from 'react';
import type { EndpointInfo, EquivalenceGroup } from '@/features/canvas/types';
import { resolveEndpointForType } from '@/features/canvas/data-workspace/query-builder/utils/queryUtils';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectDatasetGroups,
  selectDatasets,
} from '../../stores/selectors';

interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
}

interface ExistingDataset {
  id: string;
  symbol: string;
  endpoint: string;
  fields: string[];
  params: Record<string, any>;
}

interface DatasetToAdd {
  symbol: string;
  endpoint: string;
  params: Record<string, any>;
  fields: string[];
  category?: string;
}

interface UseAddDataPanelGroupsArgs {
  // Mode
  endpointSelectionMode: 'homogeneous' | 'heterogeneous';
  // Homogeneous state
  selectedEndpoint: EndpointInfo | null;
  selectedFields: string[];
  formParams: Record<string, string>;
  // Heterogeneous state
  uniqueObjectTypes: string[];
  selectedEndpointByType: Record<string, EndpointInfo | null>;
  fieldsByType: Record<string, string[]>;
  paramsByType: Record<string, Record<string, string>>;
  // Shared
  selectedObjects: SelectedObject[];
  existingDatasets: ExistingDataset[];
  equivalenceGroups: EquivalenceGroup[];
  onNavigateToDataset?: (endpoint: string) => void;
}

export function useAddDataPanelGroups({
  endpointSelectionMode,
  selectedEndpoint,
  selectedFields,
  formParams,
  uniqueObjectTypes,
  selectedEndpointByType,
  fieldsByType,
  paramsByType,
  selectedObjects,
  existingDatasets,
  equivalenceGroups,
  onNavigateToDataset,
}: UseAddDataPanelGroupsArgs) {
  const datasetGroups = useDataWorkspaceStore(selectDatasetGroups);
  const allDatasets = useDataWorkspaceStore(selectDatasets);
  const createDatasetGroup = useDataWorkspaceStore(s => s.createDatasetGroup);
  const addDatasetToGroup = useDataWorkspaceStore(s => s.addDatasetToGroup);
  const setActiveGroup = useDataWorkspaceStore(s => s.setActiveGroup);
  const updateDataset = useDataWorkspaceStore(s => s.updateDataset);

  const [adding, setAdding] = useState(false);

  // Build the list of datasets to add based on current form state
  const buildDatasetsToAdd = useCallback(() => {
    const datasets: DatasetToAdd[] = [];

    if (endpointSelectionMode === 'homogeneous') {
      if (!selectedEndpoint || selectedFields.length === 0) return datasets;

      for (const obj of selectedObjects) {
        const resolvedEndpoint = selectedEndpoint.equivalenceGroup
          ? resolveEndpointForType(selectedEndpoint.equivalenceGroup, obj.objectType, equivalenceGroups)
          : selectedEndpoint.endpoint;

        datasets.push({
          symbol: obj.symbol,
          endpoint: resolvedEndpoint,
          params: formParams,
          fields: selectedFields,
          category: selectedEndpoint.category,
        });
      }
    } else {
      for (const objType of uniqueObjectTypes) {
        const ep = selectedEndpointByType[objType];
        const fields = fieldsByType[objType] || [];
        const params = paramsByType[objType] || {};

        if (!ep || fields.length === 0) continue;

        for (const obj of selectedObjects.filter(o => o.objectType === objType)) {
          datasets.push({
            symbol: obj.symbol,
            endpoint: ep.endpoint,
            params,
            fields,
            category: ep.category,
          });
        }
      }
    }

    return datasets;
  }, [
    endpointSelectionMode,
    selectedEndpoint,
    selectedFields,
    formParams,
    selectedObjects,
    uniqueObjectTypes,
    selectedEndpointByType,
    fieldsByType,
    paramsByType,
    equivalenceGroups,
  ]);

  // Add datasets to a specific group
  const addDatasetsToGroupFn = useCallback(async (groupId: string, datasets: DatasetToAdd[]) => {
    setAdding(true);
    let addedEndpoint: string | null = null;

    try {
      for (const ds of datasets) {
        await addDatasetToGroup(groupId, ds);
        if (!addedEndpoint) {
          addedEndpoint = ds.endpoint;
        }
      }

      setActiveGroup(groupId);

      if (addedEndpoint && onNavigateToDataset) {
        onNavigateToDataset(addedEndpoint);
      }
    } catch (e) {
      console.error('Failed to add datasets to group:', e);
    } finally {
      setAdding(false);
    }
  }, [addDatasetToGroup, setActiveGroup, onNavigateToDataset]);

  // Assign groupless datasets to a group
  const assignOrphanedDatasetsToGroup = useCallback((groupId: string) => {
    const orphanedDatasets = allDatasets.filter(d => !d.groupId);
    for (const ds of orphanedDatasets) {
      updateDataset(ds.id, { groupId });
    }
  }, [allDatasets, updateDataset]);

  // Get active group ID from store
  const activeGroupId = useDataWorkspaceStore(s => s.tabs.find(t => t.id === s.activeTabId)?.activeGroupId);

  // Main add handler — always adds to the active group from the picker
  const handleAdd = useCallback(async () => {
    const datasets = buildDatasetsToAdd();
    if (datasets.length === 0) return;

    // Use active group or auto-create one
    let targetGroupId = activeGroupId;
    if (!targetGroupId || !datasetGroups.some(g => g.id === targetGroupId)) {
      targetGroupId = createDatasetGroup('Data');
    }

    // Migrate orphans
    const hasOrphans = allDatasets.some(d => !d.groupId);
    if (hasOrphans) assignOrphanedDatasetsToGroup(targetGroupId);

    await addDatasetsToGroupFn(targetGroupId, datasets);
  }, [
    buildDatasetsToAdd,
    activeGroupId,
    datasetGroups,
    allDatasets,
    createDatasetGroup,
    addDatasetsToGroupFn,
    assignOrphanedDatasetsToGroup,
  ]);

  // Check if ALL symbol+endpoint combinations already exist (homogeneous mode)
  const allCombosExistHomogeneous = useMemo(() => {
    if (!selectedEndpoint) return false;
    return selectedObjects.every(obj => {
      const resolvedEndpoint = selectedEndpoint.equivalenceGroup
        ? resolveEndpointForType(selectedEndpoint.equivalenceGroup, obj.objectType, equivalenceGroups)
        : selectedEndpoint.endpoint;
      return existingDatasets.some(d => d.endpoint === resolvedEndpoint && d.symbol === obj.symbol);
    });
  }, [selectedEndpoint, selectedObjects, existingDatasets, equivalenceGroups]);

  // Check if ALL symbol+endpoint combos exist (heterogeneous mode)
  const allCombosExistHeterogeneous = useMemo(() => {
    return uniqueObjectTypes.every(objType => {
      const ep = selectedEndpointByType[objType];
      if (!ep) return false;
      return selectedObjects
        .filter(o => o.objectType === objType)
        .every(obj => existingDatasets.some(d => d.endpoint === ep.endpoint && d.symbol === obj.symbol));
    });
  }, [uniqueObjectTypes, selectedEndpointByType, selectedObjects, existingDatasets]);

  return {
    // State
    adding,
    datasetGroups,
    allDatasets,

    // Actions
    handleAdd,
    handleAddDirect: addDatasetsToGroupFn,
    createDatasetGroup,
    assignOrphanedDatasetsToGroup,

    // Derived
    allCombosExistHomogeneous,
    allCombosExistHeterogeneous,
  };
}
