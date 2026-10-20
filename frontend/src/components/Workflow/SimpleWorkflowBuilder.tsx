import { useState } from 'react';
import api from '@/services/api';

const AGENT_OPTIONS = [
  { value: 'main_agent', label: 'Market Analyst (Main)' },
  { value: 'risk_specialist', label: 'Risk Specialist' },
  { value: 'document_analyst', label: 'Document Analyst' },
  { value: 'comparable_companies', label: 'Comparable Companies' },
  { value: 'chart_analyst', label: 'Chart Analyst' },
  { value: 'quant_coding', label: 'Quant Coding (Code Interpreter)' },
  { value: 'dcf_agent', label: 'DCF Valuation' },
  { value: 'institutional_activity', label: 'Institutional Activity' },
  { value: 'options_coding', label: 'Options Analysis' },
  { value: 'alternatives_coding', label: 'Alternatives Analysis' },
  { value: 'prediction_markets', label: 'Prediction Markets' },
];

export function SimpleWorkflowBuilder() {
  const [name, setName] = useState('My Workflow');
  const [nodes, setNodes] = useState([
    { id: '1', agent: 'main_agent', prompt: 'Get fundamentals for {input}' },
  ]);
  const [testInput, setTestInput] = useState('AAPL');

  const addNode = () => {
    const newId = String(nodes.length + 1);
    setNodes([...nodes, {
      id: newId,
      agent: 'main_agent',
      prompt: `Analyze {node_${nodes.length}}`,
    }]);
  };

  const updateNode = (index: number, field: string, value: string) => {
    const updated = [...nodes];
    updated[index] = { ...updated[index], [field]: value };
    setNodes(updated);
  };

  const removeNode = (index: number) => {
    if (nodes.length > 1) {
      setNodes(nodes.filter((_, i) => i !== index));
    }
  };

  const saveWorkflow = async () => {
    const { data } = await api.post('/api/workflows', { name, nodes });
    alert(`Workflow saved with ID: ${data.id}`);
  };

  const runWorkflow = async () => {
    // Save first
    const { data: saveData } = await api.post('/api/workflows', { name, nodes });
    const { id } = saveData;

    // Then run
    const { data: result } = await api.post(`/api/workflows/${id}/run`, { input_text: testInput });
    console.log('Workflow result:', result);
  };

  return (
    <div style={{ padding: '20px' }}>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ fontSize: '16px', marginBottom: '20px', padding: '8px', width: '100%' }}
      />

      {nodes.map((node, i) => (
        <div key={node.id} style={{
          display: 'flex',
          gap: '10px',
          marginBottom: '10px',
          padding: '10px',
          border: '1px solid #ddd',
        }}>
          <span>{i + 1}.</span>
          <select
            value={node.agent}
            onChange={(e) => updateNode(i, 'agent', e.target.value)}
            style={{ padding: '4px' }}
          >
            {AGENT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <input
            value={node.prompt}
            onChange={(e) => updateNode(i, 'prompt', e.target.value)}
            style={{ flex: 1, padding: '4px' }}
            placeholder="Enter prompt..."
          />
          {i > 0 && <button onClick={() => removeNode(i)}>X</button>}
        </div>
      ))}

      <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
        <button onClick={addNode}>+ Add Step</button>
        <button onClick={saveWorkflow}>Save</button>
        <input
          value={testInput}
          onChange={(e) => setTestInput(e.target.value)}
          placeholder="Test input"
          style={{ padding: '4px' }}
        />
        <button onClick={runWorkflow}>Run Now</button>
      </div>
    </div>
  );
}
