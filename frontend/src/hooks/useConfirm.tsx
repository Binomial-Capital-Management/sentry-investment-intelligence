import { useState, useCallback } from 'react';

// Simple confirmation hook for delete operations
export function useConfirm() {
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmCallback, setConfirmCallback] = useState<(() => void) | null>(null);

  const confirm = useCallback((callback: () => void) => {
    setIsConfirming(true);
    setConfirmCallback(() => callback);
  }, []);

  const handleConfirm = useCallback(() => {
    if (confirmCallback) {
      confirmCallback();
    }
    setIsConfirming(false);
    setConfirmCallback(null);
  }, [confirmCallback]);

  const handleCancel = useCallback(() => {
    setIsConfirming(false);
    setConfirmCallback(null);
  }, []);

  return {
    isConfirming,
    confirm,
    handleConfirm,
    handleCancel,
  };
}
