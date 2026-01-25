/**
 * PolicyConfig - UI for viewing and editing policy configuration values
 *
 * Shows live policy values that control agent behavior:
 * - Discount percentages
 * - Confidence thresholds
 * - Revenue thresholds
 */
import { useState, useEffect, useCallback } from 'react';

interface Policy {
  value: number;
  default: number;
  is_custom: boolean;
  name: string;
  description: string;
  type: string;
  min: number;
  max: number;
  unit: string;
}

interface PolicyMap {
  [key: string]: Policy;
}

export function PolicyConfig() {
  const [policies, setPolicies] = useState<PolicyMap>({});
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // Fetch policies
  const fetchPolicies = useCallback(async () => {
    try {
      const response = await fetch('/api/policies');
      const data = await response.json();
      setPolicies(data.policies || {});
    } catch (error) {
      console.error('Failed to fetch policies:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
    // Refresh every 5 seconds to catch updates from Prompt Assistant
    const interval = setInterval(fetchPolicies, 5000);
    return () => clearInterval(interval);
  }, [fetchPolicies]);

  // Start editing
  const startEdit = (key: string, policy: Policy) => {
    setEditingKey(key);
    setEditValue(policy.value.toString());
    setMessage(null);
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingKey(null);
    setEditValue('');
  };

  // Save policy
  const savePolicy = async (key: string) => {
    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch(`/api/policies/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: parseFloat(editValue) }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: data.message });
        setEditingKey(null);
        fetchPolicies();
      } else {
        setMessage({ type: 'error', text: data.detail || 'Failed to save' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setSaving(false);
    }
  };

  // Reset policy to default
  const resetPolicy = async (key: string) => {
    setSaving(true);
    try {
      const response = await fetch(`/api/policies/${key}`, { method: 'DELETE' });
      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: data.message });
        fetchPolicies();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to reset' });
    } finally {
      setSaving(false);
    }
  };

  // Group policies by category
  const discountPolicies = ['goodwill_discount_percent', 'max_discount_percent', 'min_discount_percent', 'vip_discount_percent'];
  const thresholdPolicies = ['min_confidence_threshold', 'high_confidence_threshold', 'vip_revenue_threshold'];
  const otherPolicies = Object.keys(policies).filter(k => !discountPolicies.includes(k) && !thresholdPolicies.includes(k));

  const renderPolicy = (key: string) => {
    const policy = policies[key];
    if (!policy) return null;

    const isEditing = editingKey === key;
    const displayValue = policy.type === 'decimal'
      ? `${(policy.value * 100).toFixed(0)}%`
      : policy.type === 'currency'
      ? `$${policy.value.toLocaleString()}`
      : `${policy.value}${policy.unit}`;

    return (
      <div
        key={key}
        className={`p-3 rounded-lg border transition-all ${
          policy.is_custom
            ? 'bg-cyan-900/30 border-cyan-500/50'
            : 'bg-slate-800/50 border-slate-700'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm text-slate-200">{policy.name}</span>
              {policy.is_custom && (
                <span className="text-xs bg-cyan-600 text-white px-1.5 py-0.5 rounded">Modified</span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5 truncate">{policy.description}</p>
          </div>

          {isEditing ? (
            <div className="flex items-center gap-1">
              <input
                type="number"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                step={policy.type === 'decimal' ? '0.01' : '1'}
                min={policy.min}
                max={policy.max}
                className="w-20 bg-slate-700 border border-slate-500 rounded px-2 py-1 text-sm text-white"
                autoFocus
              />
              <button
                onClick={() => savePolicy(key)}
                disabled={saving}
                className="p-1 text-emerald-400 hover:text-emerald-300"
              >
                ✓
              </button>
              <button
                onClick={cancelEdit}
                className="p-1 text-slate-400 hover:text-slate-300"
              >
                ✗
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className={`font-mono text-sm ${policy.is_custom ? 'text-cyan-300' : 'text-slate-300'}`}>
                {displayValue}
              </span>
              <button
                onClick={() => startEdit(key, policy)}
                className="p-1 text-slate-400 hover:text-white transition-colors"
                title="Edit"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              {policy.is_custom && (
                <button
                  onClick={() => resetPolicy(key)}
                  className="p-1 text-slate-400 hover:text-amber-400 transition-colors"
                  title="Reset to default"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Message */}
      {message && (
        <div className={`p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-emerald-900/50 border border-emerald-500/50 text-emerald-200'
            : 'bg-red-900/50 border border-red-500/50 text-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Discount Policies */}
      <div>
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
          <span>💰</span> Discount Policies
        </h4>
        <div className="space-y-2">
          {discountPolicies.map(renderPolicy)}
        </div>
      </div>

      {/* Threshold Policies */}
      <div>
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
          <span>📊</span> Thresholds
        </h4>
        <div className="space-y-2">
          {thresholdPolicies.map(renderPolicy)}
        </div>
      </div>

      {/* Other Policies */}
      {otherPolicies.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
            <span>⚙️</span> Other Settings
          </h4>
          <div className="space-y-2">
            {otherPolicies.map(renderPolicy)}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="bg-slate-800/30 rounded-lg p-3 text-xs text-slate-400">
        <p className="flex items-center gap-1">
          <span>💡</span>
          <span>Use the <span className="text-purple-400">Prompt Assistant</span> with admin phrase to modify these values via natural language.</span>
        </p>
      </div>
    </div>
  );
}
