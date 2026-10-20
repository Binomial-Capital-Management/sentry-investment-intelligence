import { useState, useRef, useCallback } from 'react';
import { uploadService, UploadedFile } from '@/services/upload';

const MAX_ATTACHMENTS = 10;

interface UseFileAttachmentsReturn {
  attachedFiles: UploadedFile[];
  uploadingFiles: boolean;
  isDraggingFiles: boolean;
  showDrivePicker: boolean;
  showOneDrivePicker: boolean;
  oneDriveAccountType: 'personal' | 'business' | 'sharepoint';
  showCloudMenu: boolean;
  setShowDrivePicker: (show: boolean) => void;
  setShowOneDrivePicker: (show: boolean) => void;
  setOneDriveAccountType: (type: 'personal' | 'business' | 'sharepoint') => void;
  setShowCloudMenu: (show: boolean) => void;
  clearCloudMenuTimeout: () => void;
  startCloudMenuTimeout: () => void;
  handleFileUpload: (files: File[]) => Promise<void>;
  handleFileUploadClick: () => void;
  handleRemoveFile: (fileId: string) => Promise<void>;
  handleGoogleDriveSelect: (files: any[]) => Promise<void>;
  handleOneDriveSelect: (file: File) => Promise<void>;
  clearAttachedFiles: () => void;
  dragHandlers: {
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
  };
}

export function useFileAttachments(): UseFileAttachmentsReturn {
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const [showDrivePicker, setShowDrivePicker] = useState(false);
  const [showOneDrivePicker, setShowOneDrivePicker] = useState(false);
  const [oneDriveAccountType, setOneDriveAccountType] = useState<'personal' | 'business' | 'sharepoint'>('personal');
  const [showCloudMenu, setShowCloudMenu] = useState(false);
  
  const cloudMenuTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearCloudMenuTimeout = useCallback(() => {
    if (cloudMenuTimeoutRef.current) {
      clearTimeout(cloudMenuTimeoutRef.current);
      cloudMenuTimeoutRef.current = null;
    }
  }, []);

  const startCloudMenuTimeout = useCallback(() => {
    cloudMenuTimeoutRef.current = setTimeout(() => {
      setShowCloudMenu(false);
    }, 200);
  }, []);

  const handleFileUpload = useCallback(async (files: File[]) => {
    if (files.length === 0) return;

    const remainingSlots = MAX_ATTACHMENTS - attachedFiles.length;
    if (files.length > remainingSlots) {
      files = files.slice(0, remainingSlots);
    }

    setUploadingFiles(true);
    try {
      const uploadedFiles = await uploadService.uploadFiles(files);
      setAttachedFiles(prev => [...prev, ...uploadedFiles]);
    } catch (error: any) {
      console.error('File upload failed:', error);
    } finally {
      setUploadingFiles(false);
    }
  }, [attachedFiles.length]);

  const handleFileUploadClick = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '.pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg';
    input.onchange = async (e: any) => {
      const files = Array.from(e.target.files || []) as File[];
      await handleFileUpload(files);
    };
    input.click();
  }, [handleFileUpload]);

  const handleRemoveFile = useCallback(async (fileId: string) => {
    try {
      await uploadService.deleteFile(fileId);
      setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
    } catch (error) {
      console.error('Failed to remove file:', error);
    }
  }, []);

  const handleGoogleDriveSelect = useCallback(async (files: any[]) => {
    if (files.length === 0) return;

    const remainingSlots = MAX_ATTACHMENTS - attachedFiles.length;
    if (files.length > remainingSlots) {
      files = files.slice(0, remainingSlots);
    }

    setUploadingFiles(true);
    try {
      const uploadedFiles = await uploadService.uploadFiles(files);
      setAttachedFiles(prev => [...prev, ...uploadedFiles]);
    } catch (error: any) {
      console.error('Google Drive upload failed:', error);
    } finally {
      setUploadingFiles(false);
      setShowDrivePicker(false);
    }
  }, [attachedFiles.length]);

  const handleOneDriveSelect = useCallback(async (file: File) => {
    setShowOneDrivePicker(false);
    if (attachedFiles.length >= MAX_ATTACHMENTS) {
      return;
    }

    setUploadingFiles(true);
    try {
      const uploadedFiles = await uploadService.uploadFiles([file]);
      if (uploadedFiles && uploadedFiles[0]) {
        const driveFile = { ...uploadedFiles[0], source: 'onedrive' };
        setAttachedFiles(prev => [...prev, driveFile]);
      }
    } catch (error: any) {
      console.error('Failed to upload file from OneDrive', error);
    } finally {
      setUploadingFiles(false);
    }
  }, [attachedFiles.length]);

  const clearAttachedFiles = useCallback(() => {
    setAttachedFiles([]);
  }, []);

  // Drag handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFiles(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
      setIsDraggingFiles(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFiles(false);

    if (attachedFiles.length >= MAX_ATTACHMENTS) {
      return;
    }

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await handleFileUpload(files);
    }
  }, [attachedFiles.length, handleFileUpload]);

  return {
    attachedFiles,
    uploadingFiles,
    isDraggingFiles,
    showDrivePicker,
    showOneDrivePicker,
    oneDriveAccountType,
    showCloudMenu,
    setShowDrivePicker,
    setShowOneDrivePicker,
    setOneDriveAccountType,
    setShowCloudMenu,
    clearCloudMenuTimeout,
    startCloudMenuTimeout,
    handleFileUpload,
    handleFileUploadClick,
    handleRemoveFile,
    handleGoogleDriveSelect,
    handleOneDriveSelect,
    clearAttachedFiles,
    dragHandlers: {
      onDragEnter: handleDragEnter,
      onDragLeave: handleDragLeave,
      onDragOver: handleDragOver,
      onDrop: handleDrop,
    },
  };
}
