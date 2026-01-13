import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PromptData {
  agent_id: string;
  type: 'llm' | 'rules';
  description: string;
  system_prompt?: string;
  is_custom?: boolean;
  default_prompt?: string;
  editable: boolean;
  llm_provider?: string;
}

interface Props {
  agentId: string;
  agentName: string;
  onPromptUpdated?: () => void;
}

export function PromptEditor({ agentId, agentName: _agentName, onPromptUpdated }: Props) {
  void _agentName; // Reserved for future use (e.g., display in header)
  const [promptData, setPromptData] = useState<PromptData | null>(null);
  const [editedPrompt, setEditedPrompt] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFullPrompt, setShowFullPrompt] = useState(false);

  useEffect(() => {
    fetchPrompt();
  }, [agentId]);

  const fetchPrompt = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agentId}/prompt`);
      const data = await res.json();
      setPromptData(data);
      setEditedPrompt(data.system_prompt || '');
      setError(null);
    } catch (err) {
      setError('Failed to load prompt');
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agentId}/prompt`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: editedPrompt })
      });

      if (res.ok) {
        await fetchPrompt();
        setIsEditing(false);
        onPromptUpdated?.();
      } else {
        setError('Failed to save prompt');
      }
    } catch (err) {
      setError('Failed to save prompt');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agentId}/prompt`, {
        method: 'DELETE'
      });

      if (res.ok) {
        await fetchPrompt();
        setIsEditing(false);
        onPromptUpdated?.();
      }
    } catch (err) {
      setError('Failed to reset prompt');
    } finally {
      setIsSaving(false);
    }
  };

  if (!promptData) {
    return (
      <div className="animate-pulse bg-slate-100 rounded-lg p-4 h-20"></div>
    );
  }

  // Rules-based agent - not editable
  if (promptData.type === 'rules') {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">⚡</span>
          <span className="font-medium text-slate-700">Rules-Based Agent</span>
          <span className="text-xs bg-slate-200 text-slate-600 px-2 py-0.5 rounded">Not Editable</span>
        </div>
        <p className="text-sm text-slate-500">
          {promptData.description}. This agent uses deterministic logic, not LLM prompts.
        </p>
      </div>
    );
  }

  // LLM-powered agent - show prompt and allow editing
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🧠</span>
          <span className="font-medium text-blue-700">LLM System Prompt</span>
          {promptData.is_custom && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
              Customized
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-blue-500">{promptData.llm_provider}</span>
          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-2 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200 transition-colors"
            >
              ✏️ Edit Prompt
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-3 text-sm text-red-600 bg-red-50 p-2 rounded">
          {error}
        </div>
      )}

      {isEditing ? (
        /* Editing Mode */
        <div className="space-y-3">
          <textarea
            value={editedPrompt}
            onChange={(e) => setEditedPrompt(e.target.value)}
            className="w-full h-64 p-3 text-sm font-mono bg-slate-800 text-slate-100 rounded-lg border border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter system prompt..."
          />
          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {editedPrompt.length} characters
            </div>
            <div className="flex items-center gap-2">
              {promptData.is_custom && (
                <button
                  onClick={handleReset}
                  disabled={isSaving}
                  className="px-3 py-1.5 text-sm text-amber-600 hover:bg-amber-50 rounded transition-colors"
                >
                  Reset to Default
                </button>
              )}
              <button
                onClick={() => {
                  setEditedPrompt(promptData.system_prompt || '');
                  setIsEditing(false);
                }}
                disabled={isSaving}
                className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save & Re-run'}
              </button>
            </div>
          </div>
          <div className="text-xs text-blue-600 bg-blue-100 p-2 rounded">
            💡 Tip: After saving, run the evaluation again to see how the new prompt affects the agent's reasoning.
          </div>
        </div>
      ) : (
        /* View Mode */
        <div>
          <div className="relative">
            <pre
              className={`text-xs font-mono bg-slate-800 text-slate-100 p-3 rounded-lg overflow-x-auto ${
                showFullPrompt ? 'max-h-none' : 'max-h-32'
              } overflow-y-hidden`}
            >
              {promptData.system_prompt}
            </pre>
            {!showFullPrompt && promptData.system_prompt && promptData.system_prompt.length > 500 && (
              <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-slate-800 to-transparent rounded-b-lg"></div>
            )}
          </div>
          {promptData.system_prompt && promptData.system_prompt.length > 500 && (
            <button
              onClick={() => setShowFullPrompt(!showFullPrompt)}
              className="mt-2 text-xs text-blue-600 hover:underline"
            >
              {showFullPrompt ? '▲ Show less' : '▼ Show full prompt'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
