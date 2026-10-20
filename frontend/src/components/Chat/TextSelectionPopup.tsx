import React, { useState, useEffect, useCallback, useRef } from 'react';
import MemoryIcon from '@/components/Icons/MemoryIcon';
import { motion, AnimatePresence } from 'framer-motion';
import memoryApiService from '@/services/memoryApi';

interface TextSelectionPopupProps {
  sessionId: string;
  containerRef?: React.RefObject<HTMLElement>;
}

const TextSelectionPopup: React.FC<TextSelectionPopupProps> = ({ sessionId, containerRef }) => {
  const [selectedText, setSelectedText] = useState('');
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);
  const textRef = useRef('');
  const interactingRef = useRef(false);

  const hidePopup = useCallback(() => {
    if (interactingRef.current) return;
    setSelectedText('');
    setPosition(null);
    textRef.current = '';
  }, []);

  const checkSelection = useCallback(() => {
    if (interactingRef.current) return;

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      hidePopup();
      return;
    }

    const text = selection.toString().trim();
    if (text.length < 5) {
      hidePopup();
      return;
    }

    const range = selection.getRangeAt(0);
    const container = containerRef?.current || document.body;
    
    if (!container.contains(range.commonAncestorContainer)) {
      hidePopup();
      return;
    }

    const rect = range.getBoundingClientRect();
    setPosition({
      x: rect.left + Math.min(rect.width / 2, 100),
      y: rect.top - 45,
    });
    setSelectedText(text);
    textRef.current = text;
    setShowSuccess(false);
  }, [containerRef, hidePopup]);

  useEffect(() => {
    const handleSelectionChange = () => {
      checkSelection();
    };

    const handleMouseUp = () => {
      setTimeout(checkSelection, 10);
    };

    const handleScroll = () => hidePopup();

    document.addEventListener('selectionchange', handleSelectionChange);
    document.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('scroll', handleScroll, true);
    
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
      document.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [checkSelection, hidePopup]);

  const MAX_NOTE_LENGTH = 50000;

  const handleAddToNotebook = async () => {
    const text = textRef.current || selectedText;
    if (!text || !sessionId || isAdding) return;

    const content = text.length > MAX_NOTE_LENGTH
      ? text.slice(0, MAX_NOTE_LENGTH)
      : text;
    
    setIsAdding(true);
    interactingRef.current = true;
    try {
      await memoryApiService.createNote(sessionId, {
        content,
        section: 'context',
      });
      setShowSuccess(true);
      
      window.getSelection()?.removeAllRanges();
      
      setTimeout(() => {
        interactingRef.current = false;
        setSelectedText('');
        setPosition(null);
        setShowSuccess(false);
        textRef.current = '';
      }, 1500);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      console.error('[TextSelectionPopup] Failed to add note:', detail || err);
      interactingRef.current = false;
    } finally {
      setIsAdding(false);
    }
  };

  if (!position || !selectedText) return null;

  return (
    <AnimatePresence>
      <motion.div
        ref={popupRef}
        initial={{ opacity: 0, y: 10, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.95 }}
        transition={{ duration: 0.12 }}
        style={{
          position: 'fixed',
          left: position.x,
          top: position.y,
          transform: 'translateX(-50%)',
          zIndex: 9999,
        }}
      >
        <button
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleAddToNotebook}
          disabled={isAdding}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 10px',
            background: showSuccess ? '#107C10' : '#323130',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 500,
            cursor: isAdding ? 'wait' : 'pointer',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            whiteSpace: 'nowrap',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}
        >
          <MemoryIcon size={14} />
          {showSuccess ? 'Added!' : isAdding ? 'Adding...' : 'Add to Notebook'}
        </button>
        {/* Arrow pointing down */}
        <div
          style={{
            position: 'absolute',
            bottom: '-6px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            borderTop: `6px solid ${showSuccess ? '#107C10' : '#323130'}`,
          }}
        />
      </motion.div>
    </AnimatePresence>
  );
};

export default TextSelectionPopup;

