import React, { useState, useRef } from 'react';
import { X, Upload, CheckCircle, AlertTriangle, Paperclip, Monitor, Globe } from 'lucide-react';
import { motion } from 'framer-motion';
import { useUser } from '@clerk/clerk-react';
import api from '@/services/api';
import clsx from 'clsx';

interface BugReportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Severity = 'low' | 'medium' | 'high' | 'critical';

interface Screenshot {
  file: File;
  preview: string;
}

const BugReportModal: React.FC<BugReportModalProps> = ({ isOpen, onClose }) => {
  const { user } = useUser();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState<Severity>('medium');
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const severityOptions: { value: Severity; label: string; color: string; bg: string }[] = [
    { value: 'low', label: 'Low', color: '#059669', bg: '#ECFDF5' },       // Emerald-600
    { value: 'medium', label: 'Medium', color: '#D97706', bg: '#FFFBEB' }, // Amber-600
    { value: 'high', label: 'High', color: '#EA580C', bg: '#FFF7ED' },     // Orange-600
    { value: 'critical', label: 'Critical', color: '#DC2626', bg: '#FEF2F2' }, // Red-600
  ];

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) processFiles(e.target.files);
  };

  const processFiles = (files: FileList) => {
    const newScreenshots: Screenshot[] = [];
    const maxFiles = 3 - screenshots.length;

    for (let i = 0; i < Math.min(files.length, maxFiles); i++) {
      const file = files[i];
      if (file.type.startsWith('image/') && file.size <= 10 * 1024 * 1024) {
        newScreenshots.push({
          file,
          preview: URL.createObjectURL(file),
        });
      }
    }

    setScreenshots([...screenshots, ...newScreenshots]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) processFiles(e.dataTransfer.files);
  };

  const removeScreenshot = (index: number) => {
    const updated = [...screenshots];
    URL.revokeObjectURL(updated[index].preview);
    updated.splice(index, 1);
    setScreenshots(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    setIsSubmitting(true);
    setSubmitStatus('idle');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('title', title.trim());
    formData.append('description', description.trim());
    formData.append('severity', severity);
    formData.append('page_url', window.location.href);
    formData.append('browser_info', navigator.userAgent);

    if (user?.primaryEmailAddress?.emailAddress) {
      formData.append('user_email', user.primaryEmailAddress.emailAddress);
    }
    if (user?.fullName) {
      formData.append('user_name', user.fullName);
    }

    screenshots.forEach((screenshot) => {
      formData.append('screenshots', screenshot.file);
    });

    try {
      await api.post('/api/bug-reports', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSubmitStatus('success');

      setTimeout(() => {
        handleClose(true);
      }, 2000);
    } catch (error: any) {
      setSubmitStatus('error');
      setErrorMessage(error.response?.data?.detail || 'Failed to submit report');
      setIsSubmitting(false);
    }
  };

  const handleClose = (reset: boolean = false) => {
    if (reset || !isSubmitting) {
      if (reset) {
        screenshots.forEach((s) => URL.revokeObjectURL(s.preview));
        setScreenshots([]);
        setTitle('');
        setDescription('');
        setSeverity('medium');
        setSubmitStatus('idle');
        setErrorMessage('');
      }
      onClose();
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-[2px] flex items-center justify-center z-[100] p-4 font-sans"
      onClick={handleBackdropClick}
    >
      <motion.div
        ref={modalRef}
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.98 }}
        transition={{ duration: 0.15, ease: 'easeOut' }}
        className="bg-white rounded-lg shadow-2xl w-full max-w-[580px] overflow-hidden border border-gray-200 flex flex-col max-h-[90vh]"
      >
        {/* Header - Institutional */}
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50/50 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-[18px] font-serif font-medium text-gray-900 tracking-tight flex items-center gap-2">
              System Issue Report
            </h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Globe size={10} />
                {window.location.hostname}
              </span>
              <span className="text-xs text-gray-400">|</span>
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Monitor size={10} />
                v{import.meta.env.VITE_APP_VERSION || '1.0.0'}
              </span>
            </div>
          </div>
          <button
            onClick={() => handleClose()}
            disabled={isSubmitting}
            className="text-gray-400 hover:text-gray-700 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Content */}
        <div className="p-6 space-y-6 overflow-y-auto bg-white">
          {submitStatus === 'success' ? (
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-4">
              <div className="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center border border-green-100">
                <CheckCircle size={24} className="text-green-600" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">Report Logged Successfully</h3>
                <p className="text-gray-500 text-sm mt-1">
                  Ticket ID: <span className="font-mono text-gray-700">REQ-{Math.floor(Math.random() * 10000)}</span>
                </p>
              </div>
              <p className="text-gray-500 text-xs max-w-xs">
                The engineering team has been notified. Thank you for helping maintain system integrity.
              </p>
            </div>
          ) : (
            <form id="bug-report-form" onSubmit={handleSubmit} className="space-y-6">

              {/* Title Input - Sharp & Professional */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Issue Subject</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="E.g. Data discrepancy in Portfolio Analysis..."
                  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all shadow-sm"
                  autoFocus
                  maxLength={100}
                />
              </div>

              {/* Severity Selection - Segmented Control */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Impact Level</label>
                <div className="grid grid-cols-4 gap-0 bg-gray-100 p-1 rounded-md border border-gray-200">
                  {severityOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setSeverity(option.value)}
                      className={clsx(
                        'py-1.5 text-[12px] font-medium transition-all rounded-[4px] border',
                        severity === option.value
                          ? 'bg-white border-gray-200 text-gray-900 shadow-sm'
                          : 'bg-transparent border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-200/50',
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <div className="flex items-start gap-2 mt-2 px-1">
                  <div className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{
                    backgroundColor: severityOptions.find(o => o.value === severity)?.color,
                  }} />
                  <p className="text-[11px] text-gray-500">
                    {severity === 'low' && 'Minor UI/UX issues that do not affect functionality.'}
                    {severity === 'medium' && 'Feature is working but producing incorrect or inconsistent results.'}
                    {severity === 'high' && 'Significant feature failure hindering workflow.'}
                    {severity === 'critical' && 'System outage, data loss, or critical security issue.'}
                  </p>
                </div>
              </div>

              {/* Description Textarea */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Technical Details</label>
                <div className="relative">
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="1. Steps to reproduce&#10;2. Expected behavior&#10;3. Actual behavior"
                    className="w-full px-3 py-3 bg-white border border-gray-300 rounded-md text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all min-h-[140px] resize-none shadow-sm font-mono text-[13px]"
                    maxLength={5000}
                  />
                  <div className="absolute bottom-2 right-3 text-[10px] text-gray-400 pointer-events-none font-mono">
                    {description.length}/5000 CHARS
                  </div>
                </div>
              </div>

              {/* Screenshot Upload - Technical */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider flex justify-between">
                  <span>Supporting Evidence</span>
                  <span className="font-normal normal-case">{screenshots.length}/3 files</span>
                </label>

                <div className="border border-gray-200 rounded-md overflow-hidden">
                  {screenshots.length > 0 && (
                    <div className="bg-gray-50 border-b border-gray-200 p-2 grid gap-2">
                      {screenshots.map((screenshot, index) => (
                        <div key={index} className="flex items-center justify-between bg-white border border-gray-200 rounded px-3 py-2">
                          <div className="flex items-center gap-3 overflow-hidden">
                            <div className="w-8 h-8 rounded bg-gray-100 border border-gray-200 shrink-0 overflow-hidden">
                                <img src={screenshot.preview} alt="" className="w-full h-full object-cover" />
                            </div>
                            <span className="text-xs text-gray-700 truncate font-mono max-w-[200px]">
                                {screenshot.file.name}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeScreenshot(index)}
                            className="text-gray-400 hover:text-red-600 transition-colors p-1"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {screenshots.length < 3 && (
                    <div
                      className={clsx(
                        'flex items-center justify-center py-4 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer',
                        isDragging && 'bg-blue-50',
                      )}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <div className="flex items-center gap-2 text-gray-500">
                        <Paperclip size={14} />
                        <span className="text-xs font-medium">Attach Screenshot or Logs</span>
                      </div>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={handleFileSelect}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Error Message */}
              {errorMessage && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-100 text-red-700 rounded-md text-xs">
                  <AlertTriangle size={14} className="shrink-0" />
                  <span className="font-medium">{errorMessage}</span>
                </div>
              )}
            </form>
          )}
        </div>

        {/* Footer - Structured */}
        {submitStatus !== 'success' && (
          <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between shrink-0">
            <div className="text-[10px] text-gray-400 font-mono">
              SESSION ID: {user?.id?.slice(-8) || 'ANON'}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => handleClose()}
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900 uppercase tracking-wide transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="bug-report-form"
                disabled={isSubmitting || !title.trim() || !description.trim()}
                className="px-5 py-2 bg-[#0051cc] hover:bg-[#003d99] text-white text-xs font-bold uppercase tracking-wide rounded shadow-sm transition-all disabled:opacity-50 disabled:shadow-none"
              >
                {isSubmitting ? 'Processing...' : 'Submit Report'}
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default BugReportModal;
