import { useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { toast } from 'sonner';

interface FormData {
  firstName?: string;
  lastName?: string;
  username?: string;
  publicMetadata?: Record<string, any>;
}

export const useUserUpdate = () => {
  const { user } = useUser();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateProfile = async (formData: FormData) => {
    if (!user) {
      toast.error('User not authenticated');
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      await user.update(formData);
      toast.success('Profile updated successfully');
      return true;
    } catch (err: any) {
      const errorMessage = err?.errors?.[0]?.message || 'Failed to update profile';
      setError(errorMessage);
      toast.error(errorMessage);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    updateProfile,
    isLoading,
    error,
  };
};
