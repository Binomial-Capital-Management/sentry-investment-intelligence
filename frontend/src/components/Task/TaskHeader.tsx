import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Brain, Rocket, Play, Save, Check, Loader2, CheckCircle, XCircle } from 'lucide-react';

interface TaskHeaderProps {
  taskName: string;
  onTaskNameChange: (name: string) => void;
  isDraft: boolean;
  onSave?: () => void;
  onDelete?: () => void;
  onAIAssistant?: () => void;
  onDeploy?: () => void;
  onTest?: () => void;
  onValidate?: () => void;
  activeTab?: 'history' | 'task';
  onTabChange?: (tab: 'history' | 'task') => void;
  isSaving?: boolean;
  saveSuccess?: boolean;
  isDeploying?: boolean;
  isTesting?: boolean;
  testStatus?: 'idle' | 'success' | 'failed';
  isValidating?: boolean;
  validationStatus?: 'idle' | 'valid' | 'invalid';
}

export function TaskHeader({
  taskName,
  onTaskNameChange,
  isDraft,
  onSave,
  onDelete,
  onAIAssistant,
  onDeploy,
  onTest,
  onValidate,
  activeTab = 'task',
  onTabChange,
  isSaving = false,
  saveSuccess = false,
  isDeploying = false,
  isTesting = false,
  testStatus = 'idle',
  isValidating = false,
  validationStatus = 'idle',
}: TaskHeaderProps) {
  const navigate = useNavigate();

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      height: '48px',
      background: 'rgba(249, 249, 249, 0.7)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      zIndex: 1000,
    }}>
      {/* Left Section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Back Button */}
        <button
          onClick={() => navigate('/tasks')}
          style={{
            padding: '6px',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#F1F3F4'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <ChevronLeft size={18} color="#202124" />
        </button>


        {/* Task Name Pill */}
        <span style={{
          padding: '4px 12px',
          borderRadius: '16px',
          fontSize: '14px',
          fontWeight: '500',
          color: '#202124',
          background: 'rgba(0, 0, 0, 0.05)',
        }}>
          {taskName || 'New task'}
        </span>

        {/* Draft Badge */}
        {isDraft && (
          <span style={{
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: '500',
            color: '#5F6368',
            background: '#F1F3F4',
          }}>
            Draft
          </span>
        )}
      </div>

      {/* Center Section - Tabs */}
      <div style={{
        display: 'flex',
        gap: '2px',
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
      }}>
        <button
          onClick={() => onTabChange?.('history')}
          style={{
            padding: '6px 12px',
            fontSize: '13px',
            fontWeight: activeTab === 'history' ? '500' : '400',
            background: activeTab === 'history' ? '#F1F3F4' : 'transparent',
            color: activeTab === 'history' ? '#202124' : '#5F6368',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => activeTab !== 'history' && (e.currentTarget.style.background = '#F8F9FA')}
          onMouseLeave={(e) => activeTab !== 'history' && (e.currentTarget.style.background = 'transparent')}
        >
          History
        </button>
        <button
          onClick={() => onTabChange?.('task')}
          style={{
            padding: '6px 12px',
            fontSize: '13px',
            fontWeight: activeTab === 'task' ? '500' : '400',
            background: activeTab === 'task' ? '#F1F3F4' : 'transparent',
            color: activeTab === 'task' ? '#202124' : '#5F6368',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => activeTab !== 'task' && (e.currentTarget.style.background = '#F8F9FA')}
          onMouseLeave={(e) => activeTab !== 'task' && (e.currentTarget.style.background = 'transparent')}
        >
          Task
        </button>
      </div>

      {/* Right Section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Task Assistant Button */}
        <button
          onClick={onAIAssistant}
          style={{
            padding: '6px 12px',
            background: 'transparent',
            border: '1px solid #DADCE0',
            borderRadius: '16px',
            cursor: 'pointer',
            fontSize: '13px',
            color: '#202124',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <Brain size={14} color="#5F6368" />
          Task Assistant
        </button>

        {/* Save Button */}
        <button
          onClick={onSave}
          disabled={isSaving || saveSuccess}
          style={{
            padding: '6px 12px',
            background: saveSuccess ? 'rgba(52, 168, 83, 0.1)' : 'transparent',
            border: saveSuccess ? '1px solid rgba(52, 168, 83, 0.5)' : '1px solid #DADCE0',
            borderRadius: '16px',
            cursor: (isSaving || saveSuccess) ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            color: saveSuccess ? '#34A853' : '#202124',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.3s ease',
          }}
          onMouseEnter={(e) => !isSaving && !saveSuccess && (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
          onMouseLeave={(e) => !saveSuccess && (e.currentTarget.style.background = 'transparent')}
        >
          <span
            style={{
              display: 'inline-flex',
              animation: isSaving ? 'spin 1s linear infinite' : saveSuccess ? 'checkmark 0.3s ease-out' : 'none',
            }}
          >
            {saveSuccess ? (
              <Check size={14} color="#34A853" />
            ) : (
              <Save size={14} color={saveSuccess ? '#34A853' : '#5F6368'} />
            )}
          </span>
          {saveSuccess ? 'Saved!' : isSaving ? 'Saving...' : 'Save'}
        </button>

        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }

          @keyframes checkmark {
            0% {
              transform: scale(0);
              opacity: 0;
            }
            50% {
              transform: scale(1.2);
            }
            100% {
              transform: scale(1);
              opacity: 1;
            }
          }
        `}</style>

        {/* Validate Button */}
        <button
          onClick={onValidate}
          disabled={isValidating || validationStatus !== 'idle'}
          style={{
            padding: '6px 12px',
            background:
              validationStatus === 'valid' ? 'rgba(52, 168, 83, 0.1)' :
              validationStatus === 'invalid' ? 'rgba(220, 53, 69, 0.1)' :
              'transparent',
            border:
              validationStatus === 'valid' ? '1px solid rgba(52, 168, 83, 0.5)' :
              validationStatus === 'invalid' ? '1px solid rgba(220, 53, 69, 0.5)' :
              '1px solid #DADCE0',
            borderRadius: '16px',
            cursor: (isValidating || validationStatus !== 'idle') ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            color:
              validationStatus === 'valid' ? '#34A853' :
              validationStatus === 'invalid' ? '#DC3545' :
              '#202124',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.3s ease',
          }}
          onMouseEnter={(e) => !isValidating && validationStatus === 'idle' && (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
          onMouseLeave={(e) => validationStatus === 'idle' && (e.currentTarget.style.background = 'transparent')}
        >
          <span
            style={{
              display: 'inline-flex',
              animation: isValidating ? 'spin 1s linear infinite' :
                         validationStatus === 'valid' ? 'checkmark 0.3s ease-out' :
                         validationStatus === 'invalid' ? 'shake 0.5s ease-out' :
                         'none',
            }}
          >
            {isValidating ? (
              <Loader2 size={14} />
            ) : validationStatus === 'valid' ? (
              <CheckCircle size={14} color="#34A853" />
            ) : validationStatus === 'invalid' ? (
              <XCircle size={14} color="#DC3545" />
            ) : (
              <Check size={14} color="#5F6368" />
            )}
          </span>
          {isValidating ? 'Validating...' :
           validationStatus === 'valid' ? 'Valid' :
           validationStatus === 'invalid' ? 'Invalid' :
           'Validate'}
        </button>

        {/* Test Button */}
        <button
          onClick={onTest}
          disabled={isTesting}
          style={{
            padding: '6px 12px',
            background: 'transparent',
            border: '1px solid #DADCE0',
            borderRadius: '16px',
            cursor: isTesting ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            color: '#202124',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.3s ease',
          }}
          onMouseEnter={(e) => !isTesting && testStatus === 'idle' && (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
          onMouseLeave={(e) => testStatus === 'idle' && (e.currentTarget.style.background = 'transparent')}
        >
          <span
            style={{
              display: 'inline-flex',
              animation: isTesting ? 'spin 1s linear infinite' :
                         testStatus === 'success' ? 'checkmark 0.3s ease-out' :
                         testStatus === 'failed' ? 'shake 0.5s ease-out' :
                         'none',
            }}
          >
            {isTesting ? (
              <Loader2 size={14} />
            ) : testStatus === 'success' ? (
              <CheckCircle size={14} color="#34A853" />
            ) : testStatus === 'failed' ? (
              <XCircle size={14} color="#DC3545" />
            ) : (
              <Play size={14} color="#5F6368" />
            )}
          </span>
          {isTesting ? 'Testing...' :
           testStatus === 'success' ? 'Success' :
           testStatus === 'failed' ? 'Failed' :
           'Test'}
        </button>

        {/* Deploy Button */}
        <button
          onClick={onDeploy}
          disabled={isDeploying}
          style={{
            padding: '6px 16px',
            background: '#202124',
            border: 'none',
            borderRadius: '16px',
            cursor: isDeploying ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            fontWeight: '500',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            opacity: isDeploying ? 0.8 : 1,
          }}
          onMouseEnter={(e) => !isDeploying && (e.currentTarget.style.background = '#3C4043')}
          onMouseLeave={(e) => !isDeploying && (e.currentTarget.style.background = '#202124')}
        >
          <span
            style={{
              display: 'inline-flex',
              animation: isDeploying ? 'spin 1s linear infinite' : 'none',
            }}
          >
            {isDeploying ? (
              <Loader2 size={14} color="#FFFFFF" />
            ) : (
              <Rocket size={14} color="#FFFFFF" />
            )}
          </span>
          {isDeploying ? 'Deploying...' : 'Deploy'}
        </button>
      </div>
    </div>
  );
}
