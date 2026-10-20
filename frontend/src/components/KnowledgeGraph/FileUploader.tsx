import { useState, useCallback } from 'react';
import { Upload, File, X } from 'lucide-react';

interface FileUploaderProps {
  onFileSelect: (file: File) => void;
  acceptedFormats?: string[];
}

export default function FileUploader({
  onFileSelect,
  acceptedFormats = ['.csv', '.xls', '.xlsx'],
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    const validFile = files.find(file => {
      const extension = `.${file.name.split('.').pop()?.toLowerCase()}`;
      return acceptedFormats.includes(extension);
    });

    if (validFile) {
      setSelectedFile(validFile);
      onFileSelect(validFile);
    }
  }, [acceptedFormats, onFileSelect]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const clearFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  return (
    <div className="institutional-card">
      <div
        className={`
          border-2 border-dashed rounded-lg p-8
          transition-all duration-200 ease-in-out
          ${isDragging
            ? 'border-[var(--sentry-blue)] bg-[var(--sentry-blue)]/5'
            : 'border-[var(--sentry-gray-300)] hover:border-[var(--sentry-gray-400)]'
          }
        `}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {!selectedFile ? (
          <div className="flex flex-col items-center justify-center gap-4">
            <Upload
              size={48}
              className="text-[var(--sentry-gray-500)]"
            />
            <div className="text-center">
              <p className="text-[var(--sentry-navy)] font-semibold mb-1">
                Drop your file here
              </p>
              <p className="text-[var(--sentry-gray-600)] text-sm">
                or click to browse
              </p>
              <p className="text-[var(--sentry-gray-500)] text-xs mt-2">
                Supports {acceptedFormats.join(', ')}
              </p>
            </div>
            <input
              type="file"
              accept={acceptedFormats.join(',')}
              onChange={handleFileInput}
              className="hidden"
              id="file-upload-input"
            />
            <label
              htmlFor="file-upload-input"
              className="
                px-4 py-2 rounded-md
                bg-[var(--sentry-blue)] text-white
                hover:bg-[var(--sentry-blue)]/90
                cursor-pointer transition-colors
                font-medium text-sm
              "
            >
              Select File
            </label>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <File size={32} className="text-[var(--sentry-blue)]" />
              <div>
                <p className="text-[var(--sentry-navy)] font-semibold">
                  {selectedFile.name}
                </p>
                <p className="text-[var(--sentry-gray-600)] text-sm">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={clearFile}
              className="
                p-2 rounded-md
                hover:bg-[var(--sentry-gray-200)]
                transition-colors
              "
              aria-label="Remove file"
            >
              <X size={20} className="text-[var(--sentry-gray-600)]" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
