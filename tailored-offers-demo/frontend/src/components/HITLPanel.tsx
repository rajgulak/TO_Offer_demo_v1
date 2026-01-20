import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ApprovalRequest {
  id: string;  // Backend uses 'id', not 'request_id'
  pnr: string;
  customer_name: string;
  customer_tier: string;
  proposed_offer: {
    offer_type: string;
    price: number;
    discount_percent: number;
    expected_value: number;
  };
  escalation_reasons: string[];
  risk_factors: Record<string, any>;
  status: string;
  created_at: string;
  expires_at: string;
}

interface Props {
  isEnabled: boolean;
  onApprovalComplete?: () => void;
}

export function HITLPanel({ isEnabled, onApprovalComplete }: Props) {
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(true);

  const fetchPendingApprovals = useCallback(async () => {
    if (!isEnabled) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/approvals/pending`);
      if (!response.ok) throw new Error('Failed to fetch approvals');

      const data = await response.json();
      setPendingApprovals(data.approvals || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [isEnabled]);

  // Fetch on mount and when enabled changes
  useEffect(() => {
    fetchPendingApprovals();
  }, [fetchPendingApprovals]);

  // Poll for updates every 5 seconds when enabled
  useEffect(() => {
    if (!isEnabled) return;

    const interval = setInterval(fetchPendingApprovals, 5000);
    return () => clearInterval(interval);
  }, [isEnabled, fetchPendingApprovals]);

  const handleApprove = async (requestId: string) => {
    setActionLoading(requestId);

    try {
      // First approve
      const approveResponse = await fetch(`${API_BASE}/api/approvals/${requestId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decided_by: 'demo_user',
          notes: 'Approved via demo UI',
        }),
      });

      if (!approveResponse.ok) throw new Error('Failed to approve');

      // Then resume
      const resumeResponse = await fetch(`${API_BASE}/api/approvals/${requestId}/resume`, {
        method: 'POST',
      });

      if (!resumeResponse.ok) throw new Error('Failed to resume workflow');

      // Refresh list
      await fetchPendingApprovals();
      onApprovalComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeny = async (requestId: string) => {
    setActionLoading(requestId);

    try {
      const response = await fetch(`${API_BASE}/api/approvals/${requestId}/deny`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decided_by: 'demo_user',
          notes: 'Denied via demo UI',
        }),
      });

      if (!response.ok) throw new Error('Failed to deny');

      // Refresh list
      await fetchPendingApprovals();
      onApprovalComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setActionLoading(null);
    }
  };

  if (!isEnabled) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-purple-200 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">👤</span>
          <span className="font-semibold text-gray-800">Human Approval Queue</span>
          {pendingApprovals.length > 0 && (
            <span className="bg-purple-500 text-white text-xs font-bold px-2 py-0.5 rounded-full animate-pulse">
              {pendingApprovals.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              fetchPendingApprovals();
            }}
            className="text-xs text-purple-600 hover:text-purple-800 px-2 py-1 rounded hover:bg-purple-100"
          >
            Refresh
          </button>
          <svg
            className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="p-4">
          {loading && pendingApprovals.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <div className="animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full mx-auto mb-2" />
              Loading approvals...
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-500">
              <span className="text-2xl">⚠️</span>
              <p className="mt-2">{error}</p>
              <button
                onClick={fetchPendingApprovals}
                className="mt-2 text-sm text-purple-600 hover:text-purple-800"
              >
                Retry
              </button>
            </div>
          ) : pendingApprovals.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <span className="text-4xl">✅</span>
              <p className="mt-2 font-medium">No pending approvals</p>
              <p className="text-sm">High-value offers will appear here for review</p>
            </div>
          ) : (
            <div className="space-y-4">
              {pendingApprovals.map((approval) => (
                <ApprovalCard
                  key={approval.id}
                  approval={approval}
                  onApprove={() => handleApprove(approval.id)}
                  onDeny={() => handleDeny(approval.id)}
                  isLoading={actionLoading === approval.id}
                />
              ))}
            </div>
          )}

          {/* Info Footer */}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <span>ℹ️</span>
              <p>
                Escalation rules: Offers &gt;$400, VIP customers (ConciergeKey, Executive Platinum),
                anomaly score &gt;0.8, or regulatory routes (EU, UK).
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface ApprovalCardProps {
  approval: ApprovalRequest;
  onApprove: () => void;
  onDeny: () => void;
  isLoading: boolean;
}

function ApprovalCard({ approval, onApprove, onDeny, isLoading }: ApprovalCardProps) {
  const expiresAt = new Date(approval.expires_at);
  const now = new Date();
  const minutesLeft = Math.max(0, Math.floor((expiresAt.getTime() - now.getTime()) / 60000));

  return (
    <div className="border border-purple-200 rounded-lg p-4 bg-gradient-to-r from-purple-50/50 to-white">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-600">{approval.pnr}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              approval.customer_tier === 'ConciergeKey' ? 'bg-amber-100 text-amber-700' :
              approval.customer_tier === 'Executive Platinum' ? 'bg-purple-100 text-purple-700' :
              'bg-gray-100 text-gray-600'
            }`}>
              {approval.customer_tier}
            </span>
          </div>
          <p className="text-sm font-medium text-gray-800 mt-1">{approval.customer_name}</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">Expires in</div>
          <div className={`text-sm font-medium ${minutesLeft < 5 ? 'text-red-600' : 'text-gray-700'}`}>
            {minutesLeft} min
          </div>
        </div>
      </div>

      {/* Proposed Offer */}
      <div className="bg-white rounded-lg p-3 border border-gray-200 mb-3">
        <div className="text-xs text-gray-500 mb-1">Proposed Offer</div>
        <div className="flex items-center justify-between">
          <div>
            <span className="font-medium text-gray-800">{approval.proposed_offer?.offer_type ?? 'Unknown'}</span>
            {(approval.proposed_offer?.discount_percent ?? 0) > 0 && (
              <span className="ml-2 text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">
                {((approval.proposed_offer?.discount_percent ?? 0) * 100).toFixed(0)}% off
              </span>
            )}
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-gray-800">
              ${(approval.proposed_offer?.price ?? 0).toFixed(0)}
            </div>
            <div className="text-xs text-gray-500">
              EV: ${(approval.proposed_offer?.expected_value ?? 0).toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      {/* Escalation Reasons */}
      <div className="mb-3">
        <div className="text-xs text-gray-500 mb-1">Escalation Reasons</div>
        <div className="flex flex-wrap gap-1">
          {(approval.escalation_reasons ?? []).map((reason, i) => (
            <span
              key={i}
              className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded"
            >
              {reason}
            </span>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onApprove}
          disabled={isLoading}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            isLoading
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-emerald-500 text-white hover:bg-emerald-600'
          }`}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Processing...
            </span>
          ) : (
            '✓ Approve & Send'
          )}
        </button>
        <button
          onClick={onDeny}
          disabled={isLoading}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            isLoading
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-red-500 text-white hover:bg-red-600'
          }`}
        >
          ✗ Deny
        </button>
      </div>
    </div>
  );
}
