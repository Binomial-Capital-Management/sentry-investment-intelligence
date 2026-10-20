import { useEffect, ReactNode, useState } from 'react';
import { useAuth, useClerk } from '@clerk/clerk-react';

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const { isLoaded, isSignedIn } = useAuth();
  const clerk = useClerk();
  const [orgRestored, setOrgRestored] = useState(false);

  useEffect(() => {
    if (!isSignedIn) {
      setOrgRestored(false);
    }
  }, [isSignedIn]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || orgRestored || !clerk?.setActive) return;

    const savedOrgId = localStorage.getItem('activeOrganization');

    if (savedOrgId) {
      clerk.setActive({ organization: savedOrgId })
        .then(() => setOrgRestored(true))
        .catch(() => {
          localStorage.removeItem('activeOrganization');
          setOrgRestored(true);
        });
    } else {
      setOrgRestored(true);
    }
  }, [isLoaded, isSignedIn, clerk, orgRestored]);

  return <>{children}</>;
}
