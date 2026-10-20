import { useState, useRef, useEffect } from 'react';
import { Node, Edge } from 'reactflow';
import { useWorkflowAssistant } from '../../hooks/useWorkflowAssistant';
import './WorkflowAIAssistant.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  suggestions?: WorkflowSuggestion[];
}

interface WorkflowSuggestion {
  name: string;
  description: string;
  nodes: Array<{
    type: string;
    label: string;
    position?: { x: number; y: number };
  }>;
  edges?: Array<{
    source: string;
    target: string;
  }>;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  nodes: Node[];
  edges: Edge[];
  onApplyWorkflow: (nodes: Node[], edges: Edge[]) => void;
}

export function WorkflowAIAssistant({ isOpen, onClose, nodes, edges, onApplyWorkflow }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Welcome to Sentry Workflow Support. I can help you build analysis pipelines. Try asking:\n• "Build a risk analysis workflow"\n• "Create a document processing pipeline"\n• "What does the Comparable Companies agent do?"\n• "How do I connect data sources to agents?"',
    },
  ]);
  const [input, setInput] = useState('');
  const { sendMessage, isLoading } = useWorkflowAssistant();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input;
    setInput('');

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Get context about current canvas
    const context = {
      currentNodes: nodes.map(n => ({
        type: n.type || 'unknown',
        label: n.data.label || 'Unnamed',
      })),
      currentEdges: edges.map(e => ({
        source: e.source,
        target: e.target,
      })),
    };

    try {
      // Send to backend
      const response = await sendMessage(userMessage, context);

      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.message,
        suggestions: response.suggestions,
      }]);
    } catch (error) {
      // Error handling is done in the hook
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      }]);
    }
  };

  // Function to remove JSON blocks from message content
  const cleanContent = (content: string) => {
    // Remove ```json...``` blocks but keep the rest of the message
    return content.replace(/```json[\s\S]*?```/g, '').trim();
  };

  const handleApplySuggestion = (suggestion: WorkflowSuggestion) => {
    // Generate unique IDs and positions for nodes
    const timestamp = Date.now();
    const baseX = 200;
    const baseY = 200 + (nodes.length * 50); // Offset based on existing nodes

    const newNodes = suggestion.nodes.map((n, i) => ({
      id: `ai_${timestamp}_${i}`,
      type: n.type.toLowerCase().replace(' ', '_'),
      position: n.position || { x: baseX + i * 300, y: baseY },
      data: {
        label: n.label,
        ...(n.type === 'agent' && {
          operation: 'AI Suggested',
          color: '#0078D4',
        }),
        ...(n.type === 'dataset' && {
          meta: 'AI Suggested Data',
        }),
        ...(n.type === 'output' && {
          format: 'AI Suggested Output',
        }),
      },
    }));

    // Generate edges if provided
    const newEdges = suggestion.edges?.map((e, i) => ({
      id: `ai_edge_${timestamp}_${i}`,
      source: `ai_${timestamp}_${parseInt(e.source)}`,
      target: `ai_${timestamp}_${parseInt(e.target)}`,
      type: 'smoothstep',
      animated: false,
      style: { stroke: '#C8C6C4', strokeWidth: 1.5 },
    })) || [];

    // Apply to canvas
    onApplyWorkflow(newNodes, newEdges);

    // Feedback message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `✓ Applied "${suggestion.name}" to your canvas! The workflow has been added to your canvas. You can now connect it to other nodes or modify it as needed.`,
    }]);
  };

  return (
    <div className={`workflow-ai-assistant ${isOpen ? 'open' : ''}`}>
      <div className="assistant-header">
        <div className="header-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="20" height="20">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
          </svg>
          <span>Sentry Workflow Support</span>
        </div>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="assistant-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-content">{cleanContent(msg.content)}</div>
            {msg.suggestions && msg.suggestions.map((s, j) => (
              <div key={j} className="suggestion-card">
                <h4>{s.name}</h4>
                <p>{s.description}</p>
                <button
                  className="apply-btn"
                  onClick={() => handleApplySuggestion(s)}
                >
                  Apply to Canvas →
                </button>
              </div>
            ))}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant loading">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="assistant-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask about workflows..."
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="send-btn"
        >
          {isLoading ? '...' : '→'}
        </button>
      </div>
    </div>
  );
}
