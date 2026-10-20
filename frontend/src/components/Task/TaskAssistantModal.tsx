import { useState, useRef, useEffect } from 'react';
import { X, Send, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { tasksApi } from '@/services/tasksApi';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  suggestions?: TaskSuggestion[];
}

interface TaskSuggestion {
  type: 'schedule' | 'delivery' | 'canvas' | 'validation';
  suggestion: any;
  reasoning?: string;
}

interface TaskAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentCanvas: {
    nodes: any[];
    edges: any[];
  };
  schedule?: any;
  delivery?: any;
  onApplySuggestion: (suggestion: TaskSuggestion) => void;
}

export function TaskAssistantModal({
  isOpen,
  onClose,
  currentCanvas,
  schedule,
  delivery,
  onApplySuggestion,
}: TaskAssistantModalProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      // Add welcome message
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: 'Hi! I\'m Sentry Workflow Support. I can help you build your task, suggest schedules, validate your canvas, and recommend delivery channels. What would you like help with?',
        timestamp: new Date(),
      }]);
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const data = await tasksApi.assistant(input, {
        currentNodes: currentCanvas.nodes,
        currentEdges: currentCanvas.edges,
        schedule,
        delivery,
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.message,
        timestamp: new Date(),
        suggestions: data.suggestions,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      console.error('Task assistant error:', err);
      toast.error('Failed to get response from assistant');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = (suggestion: TaskSuggestion) => {
    onApplySuggestion(suggestion);
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
    }}>
      <div style={{
        width: '500px',
        height: '100vh',
        background: '#FFFFFF',
        boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.15)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideInRight 0.3s ease-out',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #E5E7EB',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#FFFFFF',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img
              src="/binomial-icon-logo.png"
              alt="Sentry Logo"
              style={{ width: '24px', height: '24px' }}
            />
            <span style={{ fontSize: '16px', fontWeight: '600', color: '#111827' }}>
              Sentry Workflow Support
            </span>
          </div>
          <button onClick={onClose} style={{
            padding: '6px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <X size={20} style={{ color: '#6B7280' }} />
          </button>
        </div>

        {/* Messages */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          background: '#F9FAFB',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {messages.map((msg) => (
              <div key={msg.id} style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}>
                {/* Message Bubble */}
                <div style={{
                  maxWidth: '80%',
                  padding: '12px 16px',
                  borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                  background: msg.role === 'user' ? '#3B82F6' : '#FFFFFF',
                  color: msg.role === 'user' ? '#FFFFFF' : '#111827',
                  border: msg.role === 'assistant' ? '1px solid #E5E7EB' : 'none',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  {msg.content}
                </div>

                {/* Suggestions with Apply Buttons */}
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div style={{
                    marginTop: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    width: '100%',
                    maxWidth: '80%',
                  }}>
                    {msg.suggestions.map((sug, idx) => (
                      <div key={idx} style={{
                        padding: '12px',
                        background: '#FFF7ED',
                        border: '1px solid #FDBA74',
                        borderRadius: '8px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '12px',
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{
                            fontSize: '11px',
                            fontWeight: '700',
                            color: '#EA580C',
                            marginBottom: '4px',
                            letterSpacing: '0.5px',
                          }}>
                            {sug.type.toUpperCase()} SUGGESTION
                          </div>
                          {sug.reasoning && (
                            <div style={{
                              fontSize: '13px',
                              color: '#92400E',
                              lineHeight: '1.4',
                            }}>
                              {sug.reasoning}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleApply(sug)}
                          style={{
                            padding: '8px 14px',
                            background: '#3B82F6',
                            color: '#FFFFFF',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '13px',
                            fontWeight: '600',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            transition: 'all 0.2s',
                            whiteSpace: 'nowrap',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#2563EB';
                            e.currentTarget.style.transform = 'scale(1.05)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = '#3B82F6';
                            e.currentTarget.style.transform = 'scale(1)';
                          }}
                        >
                          <CheckCircle size={14} />
                          Apply
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{
                padding: '12px 16px',
                background: '#FFFFFF',
                border: '1px solid #E5E7EB',
                borderRadius: '12px 12px 12px 4px',
                maxWidth: '80%',
                color: '#6B7280',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: '#D1D5DB',
                  animation: 'pulse 1.5s ease-in-out infinite',
                }}></div>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: '#D1D5DB',
                  animation: 'pulse 1.5s ease-in-out 0.2s infinite',
                }}></div>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: '#D1D5DB',
                  animation: 'pulse 1.5s ease-in-out 0.4s infinite',
                }}></div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div style={{
          padding: '16px',
          borderTop: '1px solid #E5E7EB',
          background: '#FFFFFF',
        }}>
          <div style={{
            display: 'flex',
            gap: '8px',
            alignItems: 'center',
          }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about schedules, delivery, or canvas validation..."
              style={{
                flex: 1,
                padding: '12px 16px',
                border: '1px solid #E5E7EB',
                borderRadius: '8px',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={(e) => e.currentTarget.style.borderColor = '#3B82F6'}
              onBlur={(e) => e.currentTarget.style.borderColor = '#E5E7EB'}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              style={{
                padding: '12px 16px',
                background: !input.trim() || loading ? '#E5E7EB' : '#3B82F6',
                color: !input.trim() || loading ? '#9CA3AF' : '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                cursor: !input.trim() || loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontWeight: '600',
                fontSize: '14px',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.background = '#2563EB';
                  e.currentTarget.style.transform = 'scale(1.05)';
                }
              }}
              onMouseLeave={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.background = '#3B82F6';
                  e.currentTarget.style.transform = 'scale(1)';
                }
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>

        <style>{`
          @keyframes pulse {
            0%, 100% {
              opacity: 0.4;
              transform: scale(0.8);
            }
            50% {
              opacity: 1;
              transform: scale(1);
            }
          }

          @keyframes slideInRight {
            from {
              transform: translateX(100%);
              opacity: 0;
            }
            to {
              transform: translateX(0);
              opacity: 1;
            }
          }
        `}</style>
      </div>
    </div>
  );
}
