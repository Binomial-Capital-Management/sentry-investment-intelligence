import toast from 'react-hot-toast';
import onedriveService, { OneDriveStatus } from '@/services/onedrive';

interface EnsureOneDriveConnectionResult {
  connected: boolean;
  status: OneDriveStatus | null;
}

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 40;

export async function ensureOneDriveConnection(): Promise<EnsureOneDriveConnectionResult> {
  let status: OneDriveStatus | null = null;

  try {
    status = await onedriveService.getStatus();
  } catch (error) {
    console.error('Failed to check OneDrive status', error);
    toast.error('Unable to contact OneDrive. Please try again.');
    return { connected: false, status: null };
  }

  if (!status.enabled) {
    toast.error('OneDrive integration is disabled for this workspace.');
    return { connected: false, status };
  }

  if (status.connected) {
    return { connected: true, status };
  }

  try {
    const { authorization_url } = await onedriveService.startAuthorization();
    const popup = window.open(
      authorization_url,
      'onedrive_auth',
      'width=600,height=750,menubar=no,toolbar=no',
    );

    if (!popup) {
      toast.error('Please allow pop-ups to connect OneDrive.');
      return { connected: false, status };
    }

    return await new Promise<EnsureOneDriveConnectionResult>((resolve) => {
      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        try {
          const latest = await onedriveService.getStatus();
          status = latest;
          if (latest.connected) {
            popup.close();
            toast.success('OneDrive connected successfully.');
            resolve({ connected: true, status: latest });
            return;
          }
        } catch (error) {
          console.error('Polling OneDrive status failed', error);
        }

        if (popup.closed || attempts >= MAX_POLL_ATTEMPTS) {
          if (!popup.closed) {
            popup.close();
          }
          toast.error('OneDrive connection was not completed.');
          resolve({ connected: false, status });
          return;
        }

        setTimeout(poll, POLL_INTERVAL_MS);
      };

      setTimeout(poll, POLL_INTERVAL_MS);
    });
  } catch (error) {
    console.error('Failed to start OneDrive authorization', error);
    toast.error('Failed to start OneDrive authorization.');
    return { connected: false, status };
  }
}
