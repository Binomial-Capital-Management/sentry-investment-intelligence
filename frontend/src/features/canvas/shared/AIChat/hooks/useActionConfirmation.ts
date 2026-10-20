/**
 * useActionConfirmation - Hook for managing imperative action confirmation dialogs
 * 
 * Allows awaiting user confirmation:
 *   const confirmed = await requestConfirmation(action);
 *   if (!confirmed) return { success: false, cancelled: true };
 */

import { useState, useCallback, useRef } from 'react';
import type { AgentAction } from '../types';

// Actions that require user confirmation before execution
export const DESTRUCTIVE_ACTIONS = [
  'remove_dataset',
  'clear_workspace',
  'clear_datasets',
] as const;

export type DestructiveActionType = typeof DESTRUCTIVE_ACTIONS[number];

export function isDestructiveAction(actionType: string): boolean {
  return DESTRUCTIVE_ACTIONS.includes(actionType as DestructiveActionType);
}

interface UseActionConfirmationReturn {
  isOpen: boolean;
  pendingAction: AgentAction | null;
  requestConfirmation: (action: AgentAction) => Promise<boolean>;
  handleConfirm: () => void;
  handleCancel: () => void;
}

export function useActionConfirmation(): UseActionConfirmationReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<AgentAction | null>(null);
  
  // Store resolve function to settle the promise when user responds
  const resolveRef = useRef<((confirmed: boolean) => void) | null>(null);

  const requestConfirmation = useCallback((action: AgentAction): Promise<boolean> => {
    return new Promise((resolve) => {
      setPendingAction(action);
      setIsOpen(true);
      resolveRef.current = resolve;
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setIsOpen(false);
    setPendingAction(null);
    if (resolveRef.current) {
      resolveRef.current(true);
      resolveRef.current = null;
    }
  }, []);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    setPendingAction(null);
    if (resolveRef.current) {
      resolveRef.current(false);
      resolveRef.current = null;
    }
  }, []);

  return {
    isOpen,
    pendingAction,
    requestConfirmation,
    handleConfirm,
    handleCancel,
  };
}
