import { useEffect, useRef } from 'react';
import toast from 'react-hot-toast';

const GOOGLE_PICKER_API_KEY = import.meta.env.VITE_GOOGLE_PICKER_API_KEY as string | undefined;
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const GOOGLE_SCOPES = 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file';

declare global {
  interface Window {
    gapi: any;
    google: any;
  }
}

let gapiLoadPromise: Promise<void> | null = null;
let tokenClient: any = null;
let cachedAccessToken: string | null = null;

// Force token refresh by clearing cache
export function clearGoogleDriveCache() {
  cachedAccessToken = null;
  tokenClient = null;
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load script ${src}`));
    document.body.appendChild(script);
  });
}

async function ensureGoogleApisLoaded() {
  if (!gapiLoadPromise) {
    gapiLoadPromise = (async () => {
      await loadScript('https://apis.google.com/js/api.js');
      await loadScript('https://accounts.google.com/gsi/client');
      await new Promise<void>((resolve) => {
        window.gapi.load('client:picker', async () => {
          await window.gapi.client.init({
            apiKey: GOOGLE_PICKER_API_KEY,
            discoveryDocs: ['https://www.googleapis.com/discovery/v1/apis/drive/v3/rest'],
          });
          resolve();
        });
      });
    })();
  }
  await gapiLoadPromise;
}

interface GoogleDriveNativePickerProps {
  onSelect: (file: File) => void;
  onClose: () => void;
  allowAllFileTypes?: boolean; // If true, allow all files. If false, only spreadsheets
}

export function GoogleDriveNativePicker({ onSelect, onClose, allowAllFileTypes = false }: GoogleDriveNativePickerProps) {
  const processingRef = useRef(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    const openPicker = async () => {
      if (!GOOGLE_PICKER_API_KEY || !GOOGLE_CLIENT_ID) {
        toast.error('Google Drive picker is not configured. Please set VITE_GOOGLE_PICKER_API_KEY and VITE_GOOGLE_CLIENT_ID.');
        onClose();
        return;
      }

      try {
        await ensureGoogleApisLoaded();
      } catch (error) {
        console.error('Failed to load Google APIs', error);
        toast.error('Failed to load Google APIs.');
        onClose();
        return;
      }

      if (cancelledRef.current) return;

      if (!window.google || !window.google.picker || !window.google.accounts || !window.gapi) {
        toast.error('Google APIs did not initialize correctly.');
        onClose();
        return;
      }

      const requestAccessToken = () =>
        new Promise<string>((resolve, reject) => {
          // If we have a cached token, use it directly without requesting again
          if (cachedAccessToken) {
            resolve(cachedAccessToken);
            return;
          }

          // Create a fresh token client each time to avoid stale callbacks
          // Clear any existing one first
          tokenClient = null;
          
          tokenClient = window.google.accounts.oauth2.initTokenClient({
            client_id: GOOGLE_CLIENT_ID,
            scope: GOOGLE_SCOPES,
            callback: (tokenResponse: any) => {
              // Ignore callback if component was unmounted
              if (cancelledRef.current) {
                return;
              }
              if (tokenResponse && tokenResponse.access_token) {
                cachedAccessToken = tokenResponse.access_token;
                resolve(tokenResponse.access_token);
              } else if (tokenResponse?.error) {
                // User cancelled or auth error
                reject(new Error(tokenResponse.error));
              } else {
                reject(new Error('Failed to obtain Google access token'));
              }
            },
            error_callback: (error: any) => {
              // Handle popup closed or other errors
              if (cancelledRef.current) return;
              console.error('Google OAuth error:', error);
              reject(new Error(error?.message || 'Google authentication was cancelled'));
            },
          });
          
          // Request token - use 'select_account' instead of 'consent' for better UX
          // 'consent' forces re-consent every time, 'select_account' lets user pick account
          tokenClient.requestAccessToken({ prompt: '' });
        });

      let accessToken: string;
      try {
        accessToken = await requestAccessToken();
      } catch (error: any) {
        console.error('Failed to get access token', error);
        // Don't show error toast if user just cancelled
        if (!error?.message?.includes('cancelled') && !cancelledRef.current) {
          toast.error('Failed to authenticate with Google Drive.');
        }
        onClose();
        return;
      }

      if (cancelledRef.current) return;

      try {
        const docsView = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS);

        if (allowAllFileTypes) {
          // Allow all file types for Chat/Workflows
          docsView.setMimeTypes([
            // Spreadsheets
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'text/csv',
            // Documents
            'application/vnd.google-apps.document',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'text/plain',
            // PDFs
            'application/pdf',
            // Images
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/svg+xml',
            // JSON
            'application/json',
          ].join(','));
        } else {
          // Only spreadsheets for Knowledge Graph
          docsView.setMimeTypes([
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'text/csv',
          ].join(','));
        }
        docsView.setSelectFolderEnabled(false);

        const picker = new window.google.picker.PickerBuilder()
          .setDeveloperKey(GOOGLE_PICKER_API_KEY)
          .setOAuthToken(accessToken)
          .setOrigin(window.location.protocol + '//' + window.location.host)
          .addView(docsView)
          .setSize(window.innerWidth * 0.8, window.innerHeight * 0.8)
          .setCallback(async (data: any) => {
            if (data.action === window.google.picker.Action.PICKED) {
              // Prevent double-clicks/multiple submissions
              if (processingRef.current) {
                console.log('[Google Drive Picker] Already processing a file selection, ignoring duplicate request');
                return;
              }
              processingRef.current = true;

              const doc = data.docs && data.docs[0];
              if (!doc) {
                toast.error('No document selected.');
                processingRef.current = false;
                onClose();
                return;
              }

              // Show immediate feedback
              const loadingToast = toast.loading('Downloading file from Google Drive...');

              try {
                const file = await downloadGoogleDriveFile(doc, accessToken);
                toast.dismiss(loadingToast);
                toast.success('File downloaded successfully!');
                onSelect(file);
              } catch (error) {
                console.error('Failed to download Google Drive file', error);
                toast.dismiss(loadingToast);
                toast.error('Failed to download file from Google Drive.');
              } finally {
                processingRef.current = false;
              }
              onClose();
            } else if (data.action === window.google.picker.Action.CANCEL) {
              onClose();
            }
          })
          .build();

        picker.setVisible(true);
      } catch (error) {
        console.error('Google Drive picker error', error);
        toast.error('Failed to open Google Drive picker.');
        onClose();
      }
    };

    openPicker();

    return () => {
      cancelledRef.current = true;
      // Clear the token client to prevent stale callbacks
      tokenClient = null;
    };
  }, [onSelect, onClose, allowAllFileTypes]);

  return null;
}

async function downloadGoogleDriveFile(doc: any, accessToken: string): Promise<File> {
  const fileId = doc.id;
  const name = doc.name || 'drive-file';
  const mimeType = doc.mimeType;
  let response: Response;

  // Handle Google Workspace native formats - must be exported, not downloaded directly
  if (mimeType === 'application/vnd.google-apps.spreadsheet') {
    const exportUrl = `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
    response = await fetch(exportUrl, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      throw new Error(`Google Drive export failed with status ${response.status}`);
    }
    const blob = await response.blob();
    return new File([blob], `${name}.xlsx`, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  }

  if (mimeType === 'application/vnd.google-apps.document') {
    const exportUrl = `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=application/vnd.openxmlformats-officedocument.wordprocessingml.document`;
    response = await fetch(exportUrl, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      throw new Error(`Google Drive export failed with status ${response.status}`);
    }
    const blob = await response.blob();
    return new File([blob], `${name}.docx`, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }

  if (mimeType === 'application/vnd.google-apps.presentation') {
    const exportUrl = `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=application/vnd.openxmlformats-officedocument.presentationml.presentation`;
    response = await fetch(exportUrl, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      throw new Error(`Google Drive export failed with status ${response.status}`);
    }
    const blob = await response.blob();
    return new File([blob], `${name}.pptx`, { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' });
  }

  // For non-Google formats (PDFs, images, regular Office files, etc.), direct download works
  const downloadUrl = `https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`;
  response = await fetch(downloadUrl, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error(`Google Drive download failed with status ${response.status}`);
  }
  const blob = await response.blob();
  return new File([blob], name, { type: mimeType || blob.type || 'application/octet-stream' });
}
