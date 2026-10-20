import React, { useState } from 'react';
import { Bug } from 'lucide-react';
import BugReportModal from './BugReportModal';

interface BugReportButtonProps {
  /** Position of the floating button */
  position?: 'bottom-right' | 'bottom-left';
  /** Custom className for the button */
  className?: string;
}

/**
 * Floating bug report button that opens the bug report modal.
 * Place this component in your app layout to make it globally available.
 */
const BugReportButton: React.FC<BugReportButtonProps> = ({
  position = 'bottom-right',
  className = '',
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const positionClasses = {
    'bottom-right': 'right-6 bottom-6',
    'bottom-left': 'left-6 bottom-6',
  };

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className={`fixed ${positionClasses[position]} z-50 w-12 h-12 rounded-full bg-gray-800 hover:bg-gray-700 text-white shadow-lg hover:shadow-xl transition-all flex items-center justify-center group ${className}`}
        title="Report a Bug"
      >
        <Bug size={20} className="group-hover:scale-110 transition-transform" />
      </button>
      <BugReportModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};

export default BugReportButton;

