import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import onedriveService from '@/services/onedrive';

const ONEDRIVE_CLIENT_ID = import.meta.env.VITE_ONEDRIVE_CLIENT_ID as string | undefined;
const DEFAULT_PICKER_URL = 'https://onedrive.live.com/picker';
const SPREADSHEET_EXTENSIONS = ['csv', 'tsv', 'xls', 'xlsx', 'xlsm', 'xlsb', 'ods'];
const TRUSTED_ORIGIN_SUFFIXES = ['.sharepoint.com', '.sharepoint-df.com', '.office.com', '.office365.com', '.office.net'];

interface OneDriveNativePickerProps {
  onSelect: (file: File) => void;
  onClose: () => void;
  allowAllFileTypes?: boolean;
  accountType?: 'personal' | 'business' | 'sharepoint';
}

interface PickerCommand {
  command: 'authenticate' | 'pick' | 'close';
  items?: any[];
}

interface MessagePayload {
  type: 'initialize' | 'notification' | 'command' | 'acknowledge' | 'result' | 'activate' | 'close';
  channelId?: string;
  id?: string;
  data?: any;
}

const generateId = () => `channel-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

export function OneDriveNativePicker({ onSelect, onClose, allowAllFileTypes = false, accountType = 'personal' }: OneDriveNativePickerProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const channelIdRef = useRef(generateId());
  const portRef = useRef<MessagePort | null>(null);
  const portListenerRef = useRef<((event: MessageEvent) => void) | null>(null);
  const allowedOriginsRef = useRef<Set<string>>(new Set(['https://onedrive.live.com']));
  const lastOriginRef = useRef<string>('https://onedrive.live.com');
  const closingRef = useRef(false);
  const formSubmittedRef = useRef(false);
  const processingRef = useRef(false);

  const [pickerUrl, setPickerUrl] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  const closePicker = useCallback(() => {
    if (closingRef.current) return;
    closingRef.current = true;
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!ONEDRIVE_CLIENT_ID) {
      toast.error('OneDrive picker is not configured. Please set VITE_ONEDRIVE_CLIENT_ID.');
      closePicker();
      return;
    }

    let mounted = true;

    (async () => {
      try {
        const tokenResponse = await onedriveService.getPickerToken(accountType);
        if (!mounted) return;
        if (!tokenResponse?.access_token) {
          throw new Error('Unable to retrieve OneDrive token');
        }
        setAccessToken(tokenResponse.access_token);

        const rawUrl = tokenResponse.picker_url || tokenResponse.picker_origin || DEFAULT_PICKER_URL;
        let pickerUrlObj: URL;
        try {
          pickerUrlObj = new URL(rawUrl);
        } catch {
          pickerUrlObj = new URL(DEFAULT_PICKER_URL);
        }

      const driveMeta = tokenResponse?.drive as any || {};

      // Configure picker based on account type
      // SharePoint/business accounts need different configuration than personal OneDrive
      const isSharePoint = accountType === 'sharepoint' || accountType === 'business';

      const pickerOptions: Record<string, any> = {
        sdk: '8.0',
        authentication: {},
        messaging: {
          origin: window.location.origin,
          channelId: channelIdRef.current,
          initializeTimeout: 900000,   // 15 minutes - users need time to browse
          acknowledgeTimeout: 900000,  // 15 minutes
          resultTimeout: 900000,       // 15 minutes
        },
        search: {
          enabled: true,  // Enable native search functionality
        },
        typesAndSources: {
          mode: 'files',
          pivots: isSharePoint ? {
            // Enable navigation pivots for SharePoint/Business accounts
            oneDrive: true,           // "My files" - user's OneDrive for Business
            sharedLibraries: true,    // "Quick access" - frequently used libraries
            recent: true,             // "Recent" files
          } : {
            oneDrive: true,
            recent: true,
          },
        },
      };

      // Set entry point based on account type
      if (isSharePoint) {
        // For SharePoint/business accounts, use web URL from backend metadata
        // This prevents DefaultDocumentLibrary errors
        const webUrl = driveMeta?.web_url || driveMeta?.sharepoint_site_url;
        const siteUrl = driveMeta?.sharepoint_site_url;

        if (siteUrl) {
          // Use site URL from backend metadata
          // Navigate to SharePoint site root and let user browse
          pickerOptions.entry = {
            sharePoint: {
              byPath: {
                web: siteUrl,
                fallbackToRoot: true,
              },
            },
          };
        } else if (webUrl) {
          // Fallback: Parse the URL to separate site path from library/folder
          const url = new URL(webUrl);
          const pathParts = url.pathname.split('/').filter(p => p);

          // Check if last part is "Documents" or similar library name
          const lastPart = pathParts[pathParts.length - 1];
          const isLibraryPath = lastPart === 'Documents' || lastPart === 'Shared Documents';

          let sitePath = url.origin;
          let listName = undefined;

          if (isLibraryPath && pathParts.length > 1) {
            // Remove library name from path
            sitePath = url.origin + '/' + pathParts.slice(0, -1).join('/');
            listName = lastPart;
          } else {
            // Use full path as site
            sitePath = webUrl;
          }

          const byPathConfig: any = {
            web: sitePath,
            fallbackToRoot: true,
          };

          if (listName) {
            byPathConfig.list = listName;
          }

          pickerOptions.entry = {
            sharePoint: {
              byPath: byPathConfig,
            },
          };
        } else {
          // No SharePoint metadata available - use OneDrive entry as fallback
          pickerOptions.entry = { oneDrive: {} };
        }
      } else {
        // Consumer OneDrive - navigate to personal OneDrive
        pickerOptions.entry = { oneDrive: {} };
      }
      if (!allowAllFileTypes) {
        pickerOptions.typesAndSources.filters = {
          mode: 'include',
          includeExtensions: SPREADSHEET_EXTENSIONS,
        };
      }

        pickerUrlObj.searchParams.set('filePicker', JSON.stringify(pickerOptions));
        pickerUrlObj.searchParams.set('locale', (navigator.language || 'en-US').toLowerCase());
        pickerUrlObj.searchParams.set('sdk', '8.0');
        setPickerUrl(pickerUrlObj.toString());

        const updatedOrigins = new Set(allowedOriginsRef.current);
        updatedOrigins.add(pickerUrlObj.origin.toLowerCase());
        const extraOrigins: string[] = [];
        if (tokenResponse?.picker_origin) {
          extraOrigins.push(tokenResponse.picker_origin);
        }
        for (const originUrl of extraOrigins) {
          try {
            updatedOrigins.add(new URL(originUrl).origin.toLowerCase());
          } catch {
            // ignore
          }
        }
        allowedOriginsRef.current = updatedOrigins;

      } catch (error) {
        console.error('[OneDrive Picker] Failed to initialize:', error);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        toast.error(`Unable to connect to OneDrive: ${errorMessage}`);
        closePicker();
      }
    })();

    return () => {
      mounted = false;
    };
  }, [allowAllFileTypes, closePicker]);

  const submitPickerForm = useCallback(() => {
    if (!pickerUrl || !accessToken || !iframeRef.current || formSubmittedRef.current) {
      return;
    }

    formSubmittedRef.current = true;

    // Wait a bit to ensure message handlers are attached
    setTimeout(() => {
      try {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = pickerUrl;
        form.target = 'onedrive-picker-iframe';

        const tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = 'access_token';
        tokenInput.value = accessToken;
        form.appendChild(tokenInput);

        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);

        // Hide loading after picker should be visible (6 seconds)
        setTimeout(() => {
          setIsInitializing(false);
        }, 6000);
      } catch (error) {
        console.error('[OneDrive Picker] Failed to submit form', error);
        toast.error('Unable to start OneDrive picker.');
        setIsInitializing(false);
        closePicker();
      }
    }, 500);
  }, [pickerUrl, accessToken, closePicker]);

  useEffect(() => {
    submitPickerForm();
  }, [submitPickerForm]);

  const sendMessage = useCallback(
    (message: any, origin?: string) => {
      if (portRef.current) {
        portRef.current.postMessage(message);
      } else if (iframeRef.current?.contentWindow && (origin || lastOriginRef.current)) {
        iframeRef.current.contentWindow.postMessage(message, origin || lastOriginRef.current);
      }
    },
    [],
  );

  const handlePick = useCallback(
    async (command: PickerCommand) => {
      // Prevent double-clicks/multiple submissions
      if (processingRef.current) {
        console.log('[OneDrive Picker] Already processing a file selection, ignoring duplicate request');
        return;
      }
      processingRef.current = true;

      try {
        const items = command.items || [];

        if (!Array.isArray(items) || items.length === 0) {
          throw new Error('No file was selected');
        }
        const item = items[0];

        // Get item ID from picker response
        // SharePoint returns ID in sharepointIds.listItemUniqueId, consumer OneDrive uses id
        const itemId = item?.sharepointIds?.listItemUniqueId || item?.id;

        // Extract filename from webDavUrl since name field is undefined for SharePoint
        const fileName = item?.name ||
          (item?.webDavUrl ? item.webDavUrl.split('/').pop()?.split('?')[0] : null) ||
          'OneDrive file';

        if (!itemId) {
          throw new Error('Cannot download the selected file - missing item ID');
        }

        // Download file via backend endpoint (uses Graph API with proper auth)
        const downloadResponse = await onedriveService.downloadFile(itemId);

        const fileObj = new File([downloadResponse.blob], fileName, {
          type: downloadResponse.contentType || item?.file?.mimeType || 'application/octet-stream',
        });
        onSelect(fileObj);
        closePicker();
      } catch (error: any) {
        console.error('[OneDrive Picker] Failed to handle picked file', error);
        toast.error(error?.message || 'Unable to download file from OneDrive.');
        processingRef.current = false;
        setIsDownloading(false);
      } finally {
        processingRef.current = false;
        setIsDownloading(false);
      }
    },
    [closePicker, onSelect],
  );

  useEffect(() => {
    const handlePortMessage = (event: MessageEvent) => {
      handleMessage(event, lastOriginRef.current);
    };

    const handleMessage = (event: MessageEvent, portOrigin?: string) => {
      const iframeWindow = iframeRef.current?.contentWindow;
      if (event.source && iframeWindow && event.source !== iframeWindow) {
        return;
      }

      const origin = (portOrigin || event.origin || '').toLowerCase();
      const isAllowed = (() => {
        if (allowedOriginsRef.current.has(origin)) {
          return true;
        }
        return TRUSTED_ORIGIN_SUFFIXES.some((suffix) => origin.endsWith(suffix));
      })();
      if (!isAllowed) {
        return;
      }
      lastOriginRef.current = origin;

      const payload = event.data as MessagePayload;

      if (payload.type === 'initialize') {
        if (payload.channelId && payload.channelId !== channelIdRef.current) {
          return;
        }

        const port = event.ports && event.ports[0];
        if (port) {
          portRef.current = port;
          portListenerRef.current = (portEvent: MessageEvent) => handlePortMessage(portEvent);
          port.addEventListener('message', portListenerRef.current);
          port.start();
        }

        sendMessage({ type: 'activate' }, event.origin);
        return;
      }

      if (payload.type === 'notification') {
        if (payload.data?.error) {
          console.error('OneDrive picker error:', payload.data.error);
          const errorCode = payload.data.error.code || 'Unknown';
          const errorMsg = payload.data.error.message || 'OneDrive picker encountered an error.';
          console.error(`[OneDrive Picker] Error ${errorCode}: ${errorMsg}`);

          // Show user-friendly error message
          if (errorCode === 'unauthenticated' || errorCode === 'accessDenied') {
            toast.error('OneDrive access denied. Please reconnect your account in Settings.');
          } else {
            toast.error(`OneDrive error: ${errorMsg}`);
          }
        }
        return;
      }

      if (payload.type === 'command') {
        const command = payload.data as PickerCommand;

        // Show loading immediately for pick command (before acknowledge)
        if (command?.command === 'pick') {
          setIsDownloading(true);
        }

        sendMessage(
          {
            type: 'acknowledge',
            id: payload.id,
          },
          event.origin,
        );

        if (!command?.command) {
          return;
        }

        if (command.command === 'authenticate') {
          // Capture context BEFORE async - crucial for MessagePort/origin consistency
          const messageId = payload.id;
          const responseOrigin = event.origin;
          const capturedPort = portRef.current;
          const capturedIframe = iframeRef.current;

          (async () => {
            try {
              const tokenResponse = await onedriveService.getPickerToken(accountType);

              if (!tokenResponse?.access_token) {
                throw new Error('Unable to obtain OneDrive token');
              }

              const responseMessage = {
                type: 'result',
                id: messageId,
                data: {
                  result: 'token',
                  token: tokenResponse.access_token,
                },
              };

              // Send using captured context - not refs that might change
              if (capturedPort) {
                capturedPort.postMessage(responseMessage);
              } else if (capturedIframe?.contentWindow) {
                capturedIframe.contentWindow.postMessage(responseMessage, responseOrigin);
              } else {
                console.error('[OneDrive Picker] No valid channel to send token response');
              }
            } catch (error: any) {
              console.error('[OneDrive Picker] Failed to refresh OneDrive token:', error);

              const errorMessage = {
                type: 'result',
                id: messageId,
                data: {
                  result: 'error',
                  error: {
                    code: 'unableToObtainToken',
                    message: error?.message || 'Unable to obtain token',
                  },
                },
              };

              // Same pattern for error response
              if (capturedPort) {
                capturedPort.postMessage(errorMessage);
              } else if (capturedIframe?.contentWindow) {
                capturedIframe.contentWindow.postMessage(errorMessage, responseOrigin);
              }
            }
          })();
          return;
        }

        if (command.command === 'pick') {
          handlePick(command);
          sendMessage(
            {
              type: 'result',
              id: payload.id,
              data: { result: 'success' },
            },
            event.origin,
          );
          return;
        }

        if (command.command === 'close') {
          closePicker();
          return;
        }
      }

      if (payload.type === 'close') {
        closePicker();
      }
    };

    const windowListener = (event: MessageEvent) => handleMessage(event);
    window.addEventListener('message', windowListener);

    return () => {
      window.removeEventListener('message', windowListener);
      if (portRef.current && portListenerRef.current) {
        portRef.current.removeEventListener('message', portListenerRef.current);
        try {
          portRef.current.close();
        } catch {
          // ignore
        }
      }
      portRef.current = null;
      portListenerRef.current = null;
    };
  }, [closePicker, handlePick, sendMessage]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closePicker();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [closePicker]);

  // Render modal with iframe (like Google Drive's embedded picker)
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDownloading) {
          closePicker();
        }
      }}
    >
      <div className="relative w-[90vw] h-[90vh] max-w-[1200px] max-h-[800px] bg-white rounded-lg shadow-2xl overflow-hidden">
        <iframe
          ref={iframeRef}
          name="onedrive-picker-iframe"
          title="OneDrive File Picker"
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
        />

        {/* Loading overlay when initializing picker */}
        {isInitializing && (
          <div className="absolute inset-0 bg-white flex items-center justify-center z-10">
            <div className="flex flex-col items-center space-y-4">
              <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600"></div>
              <p className="text-gray-700 font-medium text-lg">Loading OneDrive picker...</p>
              <p className="text-gray-500 text-sm">This may take a few seconds</p>
            </div>
          </div>
        )}

        {/* Loading overlay when downloading file */}
        {isDownloading && (
          <div className="absolute inset-0 bg-black bg-opacity-60 flex items-center justify-center z-10">
            <div className="bg-white rounded-lg p-6 shadow-xl flex flex-col items-center space-y-4">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="text-gray-700 font-medium">Downloading file from OneDrive...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
