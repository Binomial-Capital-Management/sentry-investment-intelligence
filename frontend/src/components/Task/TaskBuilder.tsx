import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import {
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Edge,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import toast from 'react-hot-toast';

import { TaskHeader } from './TaskHeader';
import { TaskSidebar } from './TaskSidebar';
import { TaskCanvas } from './TaskCanvas';
import { NodeConfigPanel } from './NodeConfigPanel';
import { TaskHistory } from './TaskHistory';
import { TaskAssistantModal } from './TaskAssistantModal';
import { ValidationResultsModal } from './ValidationResultsModal';
import { tasksApi } from '@/services/tasksApi';
import type { Task } from '@/types/tasks';
import { loadTaskDraft, saveTaskDraft, clearTaskDraft } from '@/stores/taskDraftStorage';

// Initial canvas starts with a Start node
const initialNodes: Node[] = [
  {
    id: 'start-1',
    type: 'start',
    position: { x: 250, y: 100 },
    data: { label: 'Start' },
  },
];
const initialEdges: Edge[] = [];


function TaskBuilderInner() {
  const { taskId } = useParams<{ taskId: string }>();
  const { isLoaded, userId } = useAuth();
  const isNewTask = !taskId || taskId === 'new';
  const resolvedTaskId = !isNewTask ? taskId! : null;
  const navigate = useNavigate();
  const { project } = useReactFlow();
  const idRef = useRef(2);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Task configuration state
  const [taskName, setTaskName] = useState('New task');
  const [description, setDescription] = useState('');
  const [frequency, setFrequency] = useState('daily');
  const [cronExpression, setCronExpression] = useState('');
  const [email, setEmail] = useState('');
  const [deliveryPreference, setDeliveryPreference] = useState('email');
  const [isDraft, setIsDraft] = useState(true);

  // Additional task settings
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [timezone, setTimezone] = useState('America/New_York');
  const [tags, setTags] = useState<string[]>([]);
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [dayOfMonth, setDayOfMonth] = useState<number | null>(null);
  const [customCronExpression, setCustomCronExpression] = useState('');

  // Canvas state
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'success' | 'failed'>('idle');
  const [isDeploying, setIsDeploying] = useState(false);
  const [activeTab, setActiveTab] = useState<'history' | 'task'>('task');
  const [taskRuns, setTaskRuns] = useState<any[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [validationResults, setValidationResults] = useState<any>(null);
  const [validationModalOpen, setValidationModalOpen] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationStatus, setValidationStatus] = useState<'idle' | 'valid' | 'invalid'>('idle');

  // Track component mount state to distinguish initial load from user changes
  const hasMountedRef = useRef(false);

  // Cycle detection: Check if adding this edge would create a cycle
  const wouldCreateCycle = useCallback((source: string, target: string, currentEdges: Edge[]) => {
    const adjacency = new Map<string, string[]>();
    currentEdges.forEach(edge => {
      if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
      adjacency.get(edge.source)!.push(edge.target);
    });
    if (!adjacency.has(source)) adjacency.set(source, []);
    adjacency.get(source)!.push(target);

    const visited = new Set<string>();
    const stack = new Set<string>();
    const hasCycle = (nodeId: string): boolean => {
      if (stack.has(nodeId)) return true;
      if (visited.has(nodeId)) return false;
      visited.add(nodeId);
      stack.add(nodeId);
      const neighbors = adjacency.get(nodeId) || [];
      for (const neighbor of neighbors) {
        if (hasCycle(neighbor)) return true;
      }
      stack.delete(nodeId);
      return false;
    };
    return hasCycle(source);
  }, []);

  // Clean edges: Remove edges with missing nodes and cycle-creating edges
  const cleanEdges = useCallback((edgesToClean: Edge[], nodeIds: Set<string>) => {
    const removedEdges: Array<{edge: Edge, reason: string}> = [];

    // Build node type map for validation
    const nodeTypeMap = new Map<string, string>();
    nodes.forEach(node => nodeTypeMap.set(node.id, node.type));

    // First pass: Remove edges with missing nodes or invalid node types
    const validEdges = edgesToClean.filter(edge => {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        removedEdges.push({edge, reason: 'missing node'});
        return false;
      }

      // CRITICAL: End nodes cannot have outgoing edges (catches ghost edges!)
      const sourceType = nodeTypeMap.get(edge.source);
      if (sourceType === 'end') {
        removedEdges.push({edge, reason: 'end node cannot have outgoing edges'});
        return false;
      }

      // Start nodes cannot have incoming edges
      const targetType = nodeTypeMap.get(edge.target);
      if (targetType === 'start') {
        removedEdges.push({edge, reason: 'start node cannot have incoming edges'});
        return false;
      }

      return true;
    });

    // Second pass: Remove cycle-creating edges one at a time
    const cleanedEdges: Edge[] = [];
    for (const edge of validEdges) {
      if (!wouldCreateCycle(edge.source, edge.target, cleanedEdges)) {
        cleanedEdges.push(edge);
      } else {
        removedEdges.push({edge, reason: 'creates cycle'});
      }
    }

    return { cleanedEdges, removedEdges };
  }, [wouldCreateCycle, nodes]);

  // Load existing task if taskId is provided
  const draftInitializedRef = useRef(false);

  useEffect(() => {
    // Wait for auth to be loaded before making API calls
    if (!isLoaded) return;

    if (resolvedTaskId) {
      loadTask(resolvedTaskId);
      // Only load runs if we have auth
      if (userId) {
        loadTaskRuns(resolvedTaskId);
      }
      draftInitializedRef.current = true;
    } else {
      const draft = loadTaskDraft();
      if (draft) {
        applyDraft(draft);
      }
      draftInitializedRef.current = true;
    }
  }, [resolvedTaskId, isLoaded, userId]);

  // Refresh history when switching to history tab
  useEffect(() => {
    // Wait for auth before loading history
    if (activeTab === 'history' && resolvedTaskId && isLoaded && userId) {
      loadTaskRuns(resolvedTaskId);
    }
  }, [activeTab, resolvedTaskId, isLoaded, userId]);

  // Clean edges when nodes/edges change (catches ghost edges in any state update)
  const hasCleanedRef = useRef(false);
  useEffect(() => {
    // Only run once after initial load, not on every edge change
    if (hasCleanedRef.current || nodes.length === 0 || edges.length === 0) {
      return;
    }

    const nodeIds = new Set(nodes.map(n => n.id));
    const { cleanedEdges, removedEdges } = cleanEdges(edges, nodeIds);

      if (removedEdges.length > 0) {
        console.warn('Cleaned ghost edges after load:', removedEdges);
        setEdges(cleanedEdges);
        toast(
          `Fixed ${removedEdges.length} invalid connection${removedEdges.length > 1 ? 's' : ''}`,
          { duration: 2000 },
        );
        hasCleanedRef.current = true;
      }
  }, [nodes, edges, cleanEdges]); // Run when nodes/edges are loaded

  useEffect(() => {
    if (!draftInitializedRef.current) {
      return;
    }

    // Clean edges before saving to draft
    const nodeIds = new Set(nodes.map(n => n.id));
    const { cleanedEdges } = cleanEdges(edges, nodeIds);

    const draftPayload = {
      nodes,
      edges: cleanedEdges, // Save cleaned edges, not raw edges
      taskName,
      description,
      frequency,
      cronExpression,
      customCronExpression,
      email,
      deliveryPreference,
      selectedDate: selectedDate?.toISOString(),
      timezone,
      tags,
      selectedDays,
      dayOfMonth,
    };
    saveTaskDraft(draftPayload);
  }, [isNewTask, nodes, edges, taskName, description, frequency, cronExpression, customCronExpression, email, deliveryPreference, selectedDate, timezone, tags, selectedDays, dayOfMonth, cleanEdges]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  // Mark component as mounted after first render
  useEffect(() => {
    hasMountedRef.current = true;
  }, []);

  // Track nodes changes (only after mount to avoid initial load trigger)
  useEffect(() => {
    if (hasMountedRef.current) {
      setHasUnsavedChanges(true);
    }
  }, [nodes]);

  // Track edges changes (only after mount to avoid initial load trigger)
  useEffect(() => {
    if (hasMountedRef.current) {
      setHasUnsavedChanges(true);
    }
  }, [edges]);

  // Track all sidebar settings changes (only after mount to avoid initial load trigger)
  useEffect(() => {
    if (hasMountedRef.current) {
      setHasUnsavedChanges(true);
    }
  }, [
    taskName,
    description,
    frequency,
    cronExpression, // time field
    email,
    deliveryPreference,
    selectedDate,
    timezone,
    tags,
    selectedDays,
    dayOfMonth,
    customCronExpression,
  ]);

  const loadTaskRuns = async (id: string) => {
    try {
      const historyEntries = await tasksApi.getRuns(id);

      const formatOutput = (output: any) => {
        if (output === null || output === undefined) return undefined;
        if (typeof output === 'string') return output;
        try {
          return JSON.stringify(output, null, 2);
        } catch {
          return String(output);
        }
      };

      const mappedRuns = historyEntries.map(entry => {
        const run = entry.run;
        const startedAt = run.started_at || run.completed_at || run.created_at;
        const startTime = new Date(startedAt);

        const duration = run.execution_time_ms
          ? Math.floor(run.execution_time_ms / 1000)
          : run.started_at && run.completed_at
            ? Math.max(
                0,
                Math.floor(
                  (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000,
                ),
              )
            : 0;

        let status: 'success' | 'failed' | 'running' = 'running';
        if (run.status === 'completed') status = 'success';
        else if (run.status === 'failed' || run.status === 'cancelled') status = 'failed';

        const savedOutput = entry.saved_output;
        const attachments = (savedOutput?.artifacts || []).map((artifact, idx) => {
          // Build download URL using artifact metadata
          let downloadUrl: string | undefined;

          if (typeof artifact.url === 'string') {
            // Use existing URL if present
            downloadUrl = artifact.url;
          } else if (artifact.category && artifact.filename) {
            // Construct API endpoint URL for S3 download
            downloadUrl = `/api/tasks/artifacts/${artifact.category}/${artifact.filename}/download`;
          } else if (typeof artifact.path === 'string') {
            // Backward compatibility: Parse path for old artifacts without metadata
            // Path format: /tmp/{category}/{uuid}/{filename}
            const pathParts = artifact.path.split('/').filter(p => p);
            if (pathParts.length >= 3) {
              const category = pathParts[1]; // e.g., "tasks"
              const filename = pathParts[pathParts.length - 1]; // e.g., "task_workbook_20251106_174344.zip"
              downloadUrl = `/api/tasks/artifacts/${category}/${filename}/download`;
            } else {
              // If parsing fails, fall back to path (will likely fail but better than nothing)
              downloadUrl = artifact.path;
            }
          }

          return {
            name: artifact.name || `Artifact ${idx + 1}`,
            size: artifact.size ? String(artifact.size) : undefined,
            url: downloadUrl,
          };
        });

        const outputText = formatOutput(savedOutput?.output ?? run.result);

        return {
          id: run.id,
          timestamp: startTime,
          status,
          duration,
          output: outputText,
          errorMessage: run.error_message,
          attachments,
        };
      });

      setTaskRuns(mappedRuns);
    } catch (err) {
      console.error('Failed to load task runs:', err);
      // Don't show error toast - runs might not exist yet
    }
  };

  const loadTask = async (id: string) => {
    try {
      setLoading(true);
      const task = await tasksApi.get(id);

      // Load task config
      setTaskName(task.name);
      setDescription(task.description || '');
      setFrequency(task.frequency);

      // Load schedule-related fields properly
      setTimezone(task.timezone || 'America/New_York');
      setCronExpression(task.time || '');  // FIX: Load time string, NOT cron_expression
      setCustomCronExpression(task.cron_expression || '');  // Load custom cron separately
      setSelectedDays(task.days_of_week || []);
      setDayOfMonth(task.day_of_month || null);

      // Load start date if available
      if (task.start_date) {
        setSelectedDate(new Date(task.start_date));
      }

      setEmail(task.email || '');
      setDeliveryPreference(task.delivery_preference);
      setIsDraft(task.status !== 'active');

      // Load canvas data with edge cleaning
      if (task.canvas_data) {
        const canvasData = typeof task.canvas_data === 'string'
          ? JSON.parse(task.canvas_data)
          : task.canvas_data;

        if (canvasData.nodes && canvasData.edges) {
          const nodeIds = new Set(canvasData.nodes.map((n: Node) => n.id));
          const { cleanedEdges, removedEdges } = cleanEdges(canvasData.edges, nodeIds);

          // Notify user if edges were removed
          if (removedEdges.length > 0) {
            toast(
              `Fixed ${removedEdges.length} invalid connection${removedEdges.length > 1 ? 's' : ''}`,
              { duration: 3000 },
            );
            console.warn('Removed invalid edges on load:', removedEdges);
          }

          setNodes(canvasData.nodes);
          setEdges(cleanedEdges);

          // Update draft to match cleaned state
          if (removedEdges.length > 0) {
            saveTaskDraft({
              nodes: canvasData.nodes,
              edges: cleanedEdges,
              taskName,
              description,
              frequency,
              cronExpression,
              email,
              deliveryPreference,
              selectedDate: selectedDate?.toISOString(),
              timezone,
              tags,
              selectedDays,
            });
          }
        } else {
          if (canvasData.nodes) setNodes(canvasData.nodes);
          if (canvasData.edges) setEdges(canvasData.edges);
        }
      }
    } catch (err) {
      console.error('Failed to load task:', err);
      toast.error('Failed to load task');
    } finally {
      setLoading(false);
    }
  };

  const applyDraft = (draft: ReturnType<typeof loadTaskDraft>) => {
    if (!draft) return;
    setTaskName(draft.taskName || 'New task');
    setDescription(draft.description || '');
    setFrequency(draft.frequency || 'daily');
    setCronExpression(draft.cronExpression || '');
    setCustomCronExpression(draft.customCronExpression || '');
    setEmail(draft.email || '');
    setDeliveryPreference(draft.deliveryPreference || 'email');
    if (draft.selectedDate) {
      setSelectedDate(new Date(draft.selectedDate));
    }
    if (draft.timezone) {
      setTimezone(draft.timezone);
    }
    if (Array.isArray(draft.tags)) {
      setTags(draft.tags);
    }
    if (Array.isArray(draft.selectedDays)) {
      setSelectedDays(draft.selectedDays);
    }
    if (draft.dayOfMonth !== undefined && draft.dayOfMonth !== null) {
      setDayOfMonth(draft.dayOfMonth);
    }

    // Apply nodes and edges with cleaning
    if (Array.isArray(draft.nodes) && draft.nodes.length > 0 && Array.isArray(draft.edges)) {
      const nodeIds = new Set(draft.nodes.map((n: Node) => n.id));
      const { cleanedEdges, removedEdges } = cleanEdges(draft.edges, nodeIds);

      // Notify user if edges were removed from draft
      if (removedEdges.length > 0) {
        toast(
          `Fixed ${removedEdges.length} invalid connection${removedEdges.length > 1 ? 's' : ''} from draft`,
          { duration: 3000 },
        );
        console.warn('Removed invalid edges from draft:', removedEdges);
      }

      setNodes(draft.nodes);
      setEdges(cleanedEdges);
    } else {
      if (Array.isArray(draft.nodes) && draft.nodes.length > 0) {
        setNodes(draft.nodes);
      }
      if (Array.isArray(draft.edges)) {
        setEdges(draft.edges);
      }
    }
  };

  const handleSave = async (forceStatus?: 'active' | 'paused' | 'archived') => {
    try {
      setIsSaving(true);

      // Clean up edges using the same helper as load/draft
      const nodeIds = new Set(nodes.map(n => n.id));
      const { cleanedEdges, removedEdges } = cleanEdges(edges, nodeIds);

      // Update edges in state if we removed any
      if (removedEdges.length > 0) {
        setEdges(cleanedEdges);
        toast(
          `Fixed ${removedEdges.length} invalid connection${removedEdges.length > 1 ? 's' : ''}`,
          { duration: 3000 },
        );
        console.warn('Removed invalid edges on save:', removedEdges);
      }

      // Prepare canvas data
      const canvasData = {
        nodes,
        edges: cleanedEdges,
      };

      // Determine status: use forceStatus if provided, otherwise use isDraft
      const finalStatus = forceStatus || (isDraft ? 'paused' : 'active');

      // Prepare task data with complete schedule configuration
      const taskData = {
        name: taskName,
        description,
        frequency,
        timezone,
        time: cronExpression, // Time string (e.g., "02:30 PM" or "14:30")
        days_of_week: selectedDays.length > 0 ? selectedDays : undefined,
        day_of_month: dayOfMonth ?? undefined,
        start_date: selectedDate?.toISOString(),
        cron_expression: frequency === 'custom' ? customCronExpression : undefined,
        email,
        delivery_preference: deliveryPreference,
        canvas_data: canvasData,
        agent_config: {}, // Extract from nodes if needed
        status: finalStatus,
      };

      if (resolvedTaskId) {
        await tasksApi.update(resolvedTaskId, taskData);
      } else {
        const newTask = await tasksApi.create(taskData);
        toast.success('Task created');
        navigate(`/tasks/${newTask.id}`, { replace: true });
      }

      // Show success state
      setSaveSuccess(true);
      setHasUnsavedChanges(false); // Reset unsaved changes flag
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err: any) {
      console.error('Failed to save task:', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to save task';
      console.error('Error detail:', errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!resolvedTaskId) return;
    if (!confirm(`Are you sure you want to delete "${taskName}"?`)) return;

    try {
      await tasksApi.delete(resolvedTaskId);
      navigate('/tasks');
    } catch (err) {
      console.error('Failed to delete task:', err);
      toast.error('Failed to delete task');
    }
  };

  const handlePublish = async () => {
    try {
      setIsDeploying(true);

      // Pass 'active' explicitly to avoid React state timing issues
      // Add minimum delay to ensure animation is visible
      await Promise.all([
        handleSave('active'),
        new Promise(resolve => setTimeout(resolve, 800)),  // Minimum 800ms for animation
      ]);

      // Update isDraft state after successful save
      setIsDraft(false);

      // Show success feedback
      toast.success('Task deployed successfully! 🚀', { duration: 3000 });
    } catch (error) {
      console.error('Failed to deploy task:', error);
      toast.error('Failed to deploy task');
      // No need to revert isDraft since we didn't change it yet
    } finally {
      setIsDeploying(false);
    }
  };

  const handleRun = async () => {
    // Guard: Task must be saved first
    if (!resolvedTaskId) {
      console.error('[TaskBuilder] Cannot test task - task not saved yet. resolvedTaskId is null.');
      console.log('[TaskBuilder] isNewTask:', isNewTask, 'taskId:', taskId);
      toast.error('⚠️ Please save the task before testing', {
        duration: 4000,
      });
      // Briefly highlight the Save button
      toast('💡 Click the Save button first', {
        duration: 3000,
      });
      return;
    }

    // Guard: Must save changes before testing
    if (hasUnsavedChanges) {
      toast.error('⚠️ Please save your changes before testing', {
        duration: 4000,
      });
      toast('💡 Your task has unsaved changes', {
        duration: 3000,
      });
      return;
    }

    console.log('[TaskBuilder] Starting test execution for task:', resolvedTaskId);

    // Clean up any existing polling
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }

    // Reset status before starting
    setTestStatus('idle');
    setIsTesting(true);

    try {
      // Trigger the task and get the run_id
      console.log('[TaskBuilder] Calling tasksApi.trigger...');
      const execution = await tasksApi.trigger(resolvedTaskId);
      console.log('[TaskBuilder] Task triggered successfully, execution:', execution);
      console.log('[TaskBuilder] Execution ID type:', typeof execution.id, 'Value:', execution.id);

      // Poll for completion
      let hasCompleted = false; // Closure flag to prevent multiple completions

      pollIntervalRef.current = setInterval(async () => {
        if (hasCompleted) return; // Already handled, don't poll again

        try {
          const runs = await tasksApi.getRuns(resolvedTaskId, 50);
          const currentRun = runs.find(r => r.run.id === execution.id);

          if (!currentRun) {
            console.log('[TaskBuilder] Polling: Run not found yet, execution.id:', execution.id, 'available runs:', runs.map(r => r.run.id));
            return; // Not found yet, continue polling
          }

          const status = currentRun.run.status.toLowerCase(); // Normalize to lowercase
          console.log('[TaskBuilder] Polling: Found run, status:', currentRun.run.status, '(lowercase:', status, ')');

          // Check for terminal states
          if (status === 'completed' || status === 'succeeded' || status === 'success') {
            hasCompleted = true;

            // Stop polling immediately
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }

            setIsTesting(false);
            setTestStatus('success');

            // ALWAYS refresh history (not just when on history tab)
            // This ensures runs appear immediately without manual refresh
            setTaskRuns(runs);

            // Reset to idle after 5 seconds
            setTimeout(() => setTestStatus('idle'), 5000);
          } else if (status === 'failed' || status === 'error') {
            hasCompleted = true;
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }

            setIsTesting(false);
            setTestStatus('failed');
            const errorMsg = currentRun.run.error_message || 'Task execution failed';
            toast.error(errorMsg);

            // ALWAYS refresh history (not just when on history tab)
            setTaskRuns(runs);

            // Reset to idle after 5 seconds
            setTimeout(() => setTestStatus('idle'), 5000);
          }
          // If still 'queued' or 'running', keep polling
        } catch (pollError) {
          console.error('[TaskBuilder] Error polling task status:', pollError);
          // Don't stop polling on individual poll errors, backend might be temporarily busy
        }
      }, 2000); // Poll every 2 seconds

      // Safety timeout: stop polling after 5 minutes
      pollTimeoutRef.current = setTimeout(() => {
        console.warn('[TaskBuilder] Task execution timeout reached (5 minutes)');
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        if (testStatus !== 'success' && testStatus !== 'failed') {
          setIsTesting(false);
          setTestStatus('failed');
          toast.error('Task execution timeout (5 minutes)');
          setTimeout(() => setTestStatus('idle'), 5000);
        }
      }, 300000); // 5 minutes

    } catch (error: any) {
      console.error('[TaskBuilder] Error triggering task:', error);
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to trigger task';
      console.error('[TaskBuilder] Error details:', {
        status: error?.response?.status,
        data: error?.response?.data,
        message: error?.message,
      });
      toast.error(`Failed to start task: ${errorMessage}`);
      setIsTesting(false);
      setTestStatus('failed');

      // Reset to idle after 5 seconds
      setTimeout(() => setTestStatus('idle'), 5000);
    }
  };

  const handleValidate = async () => {
    if (isValidating || validationStatus !== 'idle') return;

    setIsValidating(true);

    try {
      const result = await tasksApi.validate({
        nodes,
        edges,
      });

      // Set validation status
      setValidationStatus(result.valid ? 'valid' : 'invalid');

      // Store results and open modal
      setValidationResults(result);
      setValidationModalOpen(true);

      // Display results
      if (result.valid) {
        // Validation passed - no toast needed (UI shows validation state)
      } else {
        const errorCount = result.errors.length;
        const warningCount = result.warnings.length;

        let message = `Found ${errorCount} error(s)`;
        if (warningCount > 0) {
          message += ` and ${warningCount} warning(s)`;
        }

        toast.error(message, { duration: 3000 });

        // Log detailed issues to console for debugging
        console.group('Validation Results');
        if (result.errors.length > 0) {
          console.error('Errors:', result.errors);
        }
        if (result.warnings.length > 0) {
          console.warn('Warnings:', result.warnings);
        }
        if (result.info.length > 0) {
          console.info('Suggestions:', result.info);
        }
        console.groupEnd();
      }

      // Reset validation status after 3 seconds
      setTimeout(() => {
        setValidationStatus('idle');
      }, 3000);
    } catch (error) {
      console.error('Validation error:', error);
      toast.error('Failed to validate workflow');
      setValidationStatus('invalid');

      setTimeout(() => {
        setValidationStatus('idle');
      }, 3000);
    } finally {
      setIsValidating(false);
    }
  };

  const handleAddNode = useCallback((type: string) => {
    console.log('Adding node of type:', type);
    const getId = () => `${type}-${idRef.current++}`;

    // Map node types to labels
    const labelMap: Record<string, string> = {
      start: 'Start',
      agent: 'Agent',
      end: 'End',
      merge: 'Merge',
      distribute: 'Distribute',
      portfolio: 'Portfolio',
      graph: 'Graph',
      fileUpload: 'File Upload',
      oneDrive: 'OneDrive',
      sharepoint: 'SharePoint',
      googleDrive: 'Google Drive',
      email: 'Email',
      pdfReport: 'PDF Report',
      pptPresentation: 'PPT',
      workbook: 'Workbook',
      slack: 'Slack',
      teams: 'Teams',
      saveToSentry: 'Save to Sentry',
    };

    // Find the last node to position next to
    const lastNode = nodes.length > 0 ? nodes[nodes.length - 1] : null;

    // Position directly next to the previous node
    const horizontalSpacing = 200; // Fixed spacing between nodes
    let newX, newY;

    if (lastNode) {
      // Place next to the last node
      newX = lastNode.position.x + horizontalSpacing;
      newY = lastNode.position.y;
    } else {
      // First node - center on canvas
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      newX = viewportWidth * 0.25;
      newY = viewportHeight * 0.4;
    }

    const newNode: Node = {
      id: getId(),
      type,
      position: { x: newX, y: newY },
      data: {
        label: labelMap[type] || type,
        subtitle: type === 'agent' ? 'Agent' : undefined,
      },
    };

    console.log('Created new node:', newNode);

    setNodes((nds) => {
      const updated = [...nds, newNode];
      console.log('Updated nodes:', updated);
      return updated;
    });

    // Auto-connect to the previous node with dotted pulsating line
    if (lastNode) {
      setEdges((eds) => [
        ...eds,
        {
          id: `e${lastNode.id}-${newNode.id}`,
          source: lastNode.id,
          target: newNode.id,
          type: 'smoothstep',
          animated: true,
          style: {
            stroke: '#C0C0C0',
            strokeWidth: 2,
            strokeDasharray: '5, 5',
          },
        },
      ]);
    }
  }, [nodes, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      if (!params.source || !params.target) return;

      const sourceNode = nodes.find(n => n.id === params.source);
      const targetNode = nodes.find(n => n.id === params.target);

      if (!sourceNode || !targetNode) return;

      // Remove existing edges to target ONLY if target is NOT a merge or end node
      // Merge nodes and END nodes can accept multiple inputs
      let cleanedEdges = edges;
      if (targetNode.type !== 'merge' && targetNode.type !== 'end') {
        cleanedEdges = edges.filter(e => e.target !== params.target);
      }

      // Check for cycles with cleaned edges
      if (wouldCreateCycle(params.source, params.target, cleanedEdges)) {
        toast.error('Cannot create cycle in workflow');
        return;
      }

      // Add new edge
      const newEdge = {
        ...params,
        id: `e${params.source}-${params.target}`,
        type: 'smoothstep',
        animated: true,
        style: {
          stroke: '#C0C0C0',
          strokeWidth: 2,
          strokeDasharray: '5, 5',
        },
      };

      setEdges([...cleanedEdges, newEdge]);
    },
    [setEdges, edges, nodes, wouldCreateCycle],
  );

  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      setSelectedNode(node);
    },
    [],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleUpdateNode = useCallback(
    (nodeId: string, data: any) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            const updatedNode = { ...node, data };
            // Also update selectedNode if it's the same node
            if (selectedNode?.id === nodeId) {
              setSelectedNode(updatedNode);
            }
            return updatedNode;
          }
          return node;
        }),
      );
    },
    [setNodes, selectedNode],
  );

  const handleDeleteSelected = useCallback(() => {
    setNodes((nds) => nds.filter((node) => !node.selected));
    setEdges((eds) => eds.filter((edge) => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      return !sourceNode?.selected && !targetNode?.selected;
    }));
  }, [setNodes, setEdges, nodes]);

  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    setSelectedNode(null);
  }, [setNodes, setEdges]);

  // Handle node deletion from ReactFlow (Delete key, etc.)
  const onNodesDelete = useCallback((deleted: Node[]) => {
    const deletedIds = new Set(deleted.map(n => n.id));

    // Remove all edges connected to deleted nodes
    setEdges(edges =>
      edges.filter(e => !deletedIds.has(e.source) && !deletedIds.has(e.target)),
    );
  }, [setEdges]);

  const handleApplySuggestion = useCallback((suggestion: any) => {
    switch (suggestion.type) {
      case 'schedule':
        if (suggestion.suggestion.frequency) setFrequency(suggestion.suggestion.frequency);
        if (suggestion.suggestion.time) {
          // Handle time field if you have it in state
          // For now, if it's a cron expression
          if (suggestion.suggestion.cron_expression) {
            setCronExpression(suggestion.suggestion.cron_expression);
            setFrequency('custom');
          }
        }
        break;
      case 'delivery':
        if (suggestion.suggestion.channel) {
          setDeliveryPreference(suggestion.suggestion.channel);
        }
        break;
      case 'canvas':
        // Check if this is a complete workflow or simple node additions
        if (suggestion.suggestion.workflow) {
          // Complete workflow replacement
          const workflow = suggestion.suggestion.workflow;
          const timestamp = Date.now();
          const newNodes: any[] = [];
          const newEdges: any[] = [];

          // Create nodes from workflow
          workflow.nodes.forEach((node: any, index: number) => {
            const nodeId = `${node.type}-${timestamp}-${index}`;
            newNodes.push({
              id: nodeId,
              type: node.type,
              position: { x: 250 + index * 200, y: 100 },
              data: {
                label: node.label,
                ...node.config,
              },
            });
          });

          // Create edges from workflow (map indices to actual node IDs)
          if (workflow.edges) {
            workflow.edges.forEach((edge: any, edgeIndex: number) => {
              const sourceNode = newNodes[edge.source];
              const targetNode = newNodes[edge.target];
              if (sourceNode && targetNode) {
                newEdges.push({
                  id: `e${timestamp}-${edgeIndex}`,
                  source: sourceNode.id,
                  target: targetNode.id,
                  type: 'smoothstep',
                  animated: true,
                  style: {
                    stroke: '#C0C0C0',
                    strokeWidth: 2,
                    strokeDasharray: '5, 5',
                  },
                });
              }
            });
          }

          // Replace entire canvas
          setNodes(newNodes);
          setEdges(newEdges);
        } else if (suggestion.suggestion.addNodes) {
          // Simple node additions (append to existing canvas)
          const nodesToAdd = suggestion.suggestion.addNodes;
          const newNodes: any[] = [];
          const newEdges: any[] = [];

          // Find last node position for placement
          const lastNode = nodes.length > 0 ? nodes[nodes.length - 1] : null;
          let currentX = lastNode ? lastNode.position.x + 200 : 250;
          const currentY = lastNode ? lastNode.position.y : 100;

          nodesToAdd.forEach((nodeType: string, index: number) => {
            const nodeId = `${nodeType}-${idRef.current++}`;
            const labelMap: Record<string, string> = {
              start: 'Start',
              end: 'End',
              agent: 'Agent',
              merge: 'Merge',
              distribute: 'Distribute',
              portfolio: 'Portfolio',
              fileUpload: 'File Upload',
              oneDrive: 'OneDrive',
              sharepoint: 'SharePoint',
              googleDrive: 'Google Drive',
              email: 'Email',
              slack: 'Slack',
              teams: 'Teams',
              saveToSentry: 'Save to Sentry',
              pdfReport: 'PDF Report',
              pptPresentation: 'PPT',
              workbook: 'Workbook',
            };

            newNodes.push({
              id: nodeId,
              type: nodeType,
              position: { x: currentX, y: currentY },
              data: { label: labelMap[nodeType] || nodeType },
            });

            // Auto-connect to previous node
            if (lastNode || index > 0) {
              const sourceId = index === 0 && lastNode ? lastNode.id : newNodes[index - 1].id;
              newEdges.push({
                id: `e${sourceId}-${nodeId}`,
                source: sourceId,
                target: nodeId,
                type: 'smoothstep',
                animated: true,
                style: {
                  stroke: '#C0C0C0',
                  strokeWidth: 2,
                  strokeDasharray: '5, 5',
                },
              });
            }

            currentX += 200;
          });

          // Append to existing canvas
          setNodes((nds) => [...nds, ...newNodes]);
          setEdges((eds) => [...eds, ...newEdges]);
        }
        break;
      case 'validation':
        // Handle validation feedback - just notify user
        break;
      default:
        console.warn('Unknown suggestion type:', suggestion.type);
    }
  }, [setFrequency, setCronExpression, setDeliveryPreference, setNodes, setEdges, nodes, idRef]);

  if (loading) {
    return (
      <div style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#F0F0F0',
      }}>
        <div style={{ fontSize: '14px', color: '#6C6C6C' }}>Loading task...</div>
      </div>
    );
  }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#F0F0F0',
    }}>
      {/* Header */}
      <TaskHeader
        taskName={taskName}
        onTaskNameChange={setTaskName}
        isDraft={isDraft}
        onSave={() => handleSave()}
        onDelete={resolvedTaskId ? handleDelete : undefined}
        onAIAssistant={() => setAssistantOpen(true)}
        onDeploy={handlePublish}
        onTest={handleRun}
        onValidate={handleValidate}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isSaving={isSaving}
        saveSuccess={saveSuccess}
        isTesting={isTesting}
        testStatus={testStatus}
        isValidating={isValidating}
        validationStatus={validationStatus}
        isDeploying={isDeploying}
      />

      {/* Main Content - Conditional Render based on Active Tab */}
      {activeTab === 'history' ? (
        <TaskHistory runs={taskRuns} />
      ) : (
        <div style={{
          flex: 1,
          position: 'relative',
          background: '#F8F8F8',
          overflow: 'hidden',
        }}>
          {/* Canvas - Full Width */}
          <TaskCanvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodesDelete={onNodesDelete}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onSave={handleSave}
            onRun={handleRun}
            onDeleteSelected={handleDeleteSelected}
            selectionMode={selectionMode}
            onSelectionModeChange={setSelectionMode}
          />

          {/* Left Floating Sidebar Components */}
          <TaskSidebar
            taskName={taskName}
            onTaskNameChange={setTaskName}
            description={description}
            onDescriptionChange={setDescription}
            frequency={frequency}
            onFrequencyChange={setFrequency}
            cronExpression={cronExpression}
            onCronExpressionChange={setCronExpression}
            customCronExpression={customCronExpression}
            onCustomCronExpressionChange={setCustomCronExpression}
            email={email}
            onEmailChange={setEmail}
            deliveryPreference={deliveryPreference}
            onDeliveryPreferenceChange={setDeliveryPreference}
            onAddNode={handleAddNode}
            selectedDate={selectedDate}
            onSelectedDateChange={setSelectedDate}
            timezone={timezone}
            onTimezoneChange={setTimezone}
            tags={tags}
            onTagsChange={setTags}
            selectedDays={selectedDays}
            onSelectedDaysChange={setSelectedDays}
            dayOfMonth={dayOfMonth}
            onDayOfMonthChange={setDayOfMonth}
          />

          {/* Right Floating Panel - Node Configuration (conditional) */}
          {selectedNode && (
            <div style={{
              position: 'absolute',
              top: '80px',
              right: '16px',
              bottom: '16px',
              zIndex: 5,
            }}>
              <NodeConfigPanel
                selectedNode={selectedNode}
                onUpdateNode={handleUpdateNode}
                onDeleteNode={handleDeleteNode}
                onClose={() => setSelectedNode(null)}
              />
            </div>
          )}
        </div>
      )}

      {/* Task Assistant Modal */}
      <TaskAssistantModal
        isOpen={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        currentCanvas={{ nodes, edges }}
        schedule={{ frequency, time: cronExpression, timezone: 'UTC' }}
        delivery={{ primary_channel: deliveryPreference }}
        onApplySuggestion={handleApplySuggestion}
      />

      {/* Validation Results Modal */}
      <ValidationResultsModal
        isOpen={validationModalOpen}
        onClose={() => setValidationModalOpen(false)}
        results={validationResults}
        onFixIssue={(nodeId) => {
          // Find and select the node to help user fix it
          const node = nodes.find(n => n.id === nodeId);
          if (node) {
            setSelectedNode(node);
            setValidationModalOpen(false);
            toast(`Selected node: ${node.data?.label || node.type}`);
          }
        }}
      />
    </div>
  );
}

// Wrapper with ReactFlowProvider
export default function TaskBuilder() {
  return (
    <ReactFlowProvider>
      <TaskBuilderInner />
    </ReactFlowProvider>
  );
}
