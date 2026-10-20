import toast from 'react-hot-toast';
import googleDriveService, { DriveStatus } from '@/services/googleDrive';

interface EnsureDriveConnectionResult {
  connected: boolean;
  status: DriveStatus | null;
}

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 40; // ~60 seconds

export async function ensureDriveConnection(): Promise<EnsureDriveConnectionResult> {
  let status: DriveStatus | null = null;

  try {
    status = await googleDriveService.getStatus();
  } catch (error) {
    console.error('Failed to check Google Drive status', error);
    toast.error('Unable to contact Google Drive. Please try again.');
    return { connected: false, status: null };
  }

  if (!status.enabled) {
    toast.error('Google Drive integration is disabled for this workspace.');
    return { connected: false, status };
  }

  if (status.connected) {
    return { connected: true, status };
  }

  // Need to start OAuth flow
  try {
    const { authorization_url } = await googleDriveService.startAuthorization();

    const popup = window.open(
      authorization_url,
      'google_drive_auth',
      'width=600,height=750,menubar=no,toolbar=no',
    );

    if (!popup) {
      toast.error('Please allow pop-ups to connect Google Drive.');
      return { connected: false, status };
    }

    // Poll for connection status until user finishes auth or closes popup
    return await new Promise<EnsureDriveConnectionResult>((resolve) => {
      let attempts = 0;

      const poll = async () => {
        attempts += 1;

        try {
          const latest = await googleDriveService.getStatus();
          status = latest;

          if (latest.connected) {
            popup.close();
            toast.success('Google Drive connected successfully.');
            resolve({ connected: true, status: latest });
            return;
          }
        } catch (error) {
          console.error('Polling Google Drive status failed', error);
        }

        if (popup.closed || attempts >= MAX_POLL_ATTEMPTS) {
          if (!popup.closed) {
            popup.close();
          }
          toast.error('Google Drive connection was not completed.');
          resolve({ connected: false, status });
          return;
        }

        setTimeout(poll, POLL_INTERVAL_MS);
      };

      setTimeout(poll, POLL_INTERVAL_MS);
    });
  } catch (error) {
    console.error('Failed to start Google Drive authorization', error);
    toast.error('Failed to start Google Drive authorization.');
    return { connected: false, status };
  }
}

