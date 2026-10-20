import { useState } from 'react';
import axios from 'axios';
import { API_BASE } from '@/services/api';

interface WorkflowContext {
  currentNodes: Array<{ type: string; label: string }>;
  currentEdges: Array<{ source: string; target: string }>;
}

interface AssistantResponse {
  message: string;
  suggestions?: Array<{
    name: string;
    description: string;
    nodes: Array<{ type: string; label: string }>;
    edges?: Array<{ source: string; target: string }>;
  }>;
}

export function useWorkflowAssistant() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async (
    message: string,
    context: WorkflowContext,
  ): Promise<AssistantResponse> => {
    setIsLoading(true);
    setError(null);

    try {
      // Get or create session ID for conversation continuity
      let sessionId = localStorage.getItem('workflow_assistant_session');
      if (!sessionId) {
        sessionId = `wa_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem('workflow_assistant_session', sessionId);
      }

      // Make request to workflow assistant endpoint
      const response = await axios.post(
        `${API_BASE}/api/workflow/assistant`,
        {
          message,
          context,
          session_id: sessionId,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            // Add auth token if available
            ...(localStorage.getItem('auth-token') && {
              'Authorization': `Bearer ${localStorage.getItem('auth-token')}`,
            }),
          },
          timeout: 30000, // 30 second timeout for AI responses
        },
      );

      return response.data;
    } catch (err: any) {
      console.error('Workflow assistant error:', err);

      // Extract error message
      const errorMsg = err.response?.data?.detail ||
                      err.message ||
                      'Failed to get response from assistant';
      setError(errorMsg);

      // Return error as message
      return {
        message: `Sorry, I encountered an error: ${errorMsg}. Please try again.`,
        suggestions: [],
      };
    } finally {
      setIsLoading(false);
    }
  };

  // Clear session (for starting fresh conversations)
  const clearSession = () => {
    localStorage.removeItem('workflow_assistant_session');
  };

  return {
    sendMessage,
    isLoading,
    error,
    clearSession,
  };
}
