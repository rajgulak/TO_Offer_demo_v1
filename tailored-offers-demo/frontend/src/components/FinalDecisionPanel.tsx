import { useState } from 'react';
import type { FinalDecision } from '../types';

interface Props {
  decision: FinalDecision | null;
  isComplete: boolean;
}

export function FinalDecisionPanel({ decision, isComplete }: Props) {
  const [showMessage, setShowMessage] = useState(false);

  if (!isComplete) {
    return null;
  }

  if (!decision) {
    return (
      <div className="bg-gray-100 rounded-xl border border-gray-200 p-6 text-center text-gray-500">
        Waiting for evaluation...
      </div>
    );
  }

  if (!decision.should_send_offer) {
    return (
      <div className="bg-amber-50 rounded-xl border border-amber-200 p-6 animate-slide-up">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
            <span className="text-2xl">🚫</span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-amber-800">No Offer</h3>
            <p className="text-amber-600">{decision.suppression_reason}</p>
          </div>
        </div>
        <p className="text-sm text-amber-700">
          The agent pipeline determined that sending an offer is not appropriate for this customer at this time.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-emerald-50 rounded-xl border border-emerald-200 overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="bg-emerald-100 px-6 py-4 border-b border-emerald-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-emerald-200 flex items-center justify-center">
              <span className="text-2xl">✅</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-emerald-800">Send Offer</h3>
              <p className="text-emerald-600">Offer ready for delivery</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-emerald-700">
              ${decision.price?.toFixed(0)}
            </div>
            {decision.discount_percent && decision.discount_percent > 0 && (
              <div className="text-sm text-emerald-600">
                {(decision.discount_percent * 100).toFixed(0)}% discount applied
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg p-3 border border-emerald-100">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Offer Type</div>
            <div className="text-lg font-semibold text-gray-800">{decision.offer_type}</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-emerald-100">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Channel</div>
            <div className="text-lg font-semibold text-gray-800 capitalize">{decision.channel}</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-emerald-100">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Send Time</div>
            <div className="text-lg font-semibold text-gray-800">{decision.send_time}</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-emerald-100">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Experiment</div>
            <div className="text-lg font-semibold text-gray-800">{decision.experiment_group}</div>
          </div>
        </div>

        {/* Fallback offer */}
        {decision.fallback_offer && (
          <div className="bg-white rounded-lg p-3 border border-emerald-100 mb-6">
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Fallback Offer</div>
            <div className="text-sm text-gray-700">
              {decision.fallback_offer.display_name} @ ${decision.fallback_offer.price}
            </div>
          </div>
        )}

        {/* Tracking ID */}
        <div className="bg-gray-100 rounded-lg p-3 mb-6">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Tracking ID</div>
          <code className="text-xs text-gray-600 break-all">{decision.tracking_id}</code>
        </div>

        {/* Message preview button */}
        <button
          onClick={() => setShowMessage(!showMessage)}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
        >
          {showMessage ? 'Hide Message Preview' : 'Show Message Preview'}
        </button>

        {/* Message preview */}
        {showMessage && decision.message_subject && (
          <div className="mt-4 bg-white rounded-lg border border-gray-200 overflow-hidden">
            {/* Email header mockup */}
            <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center text-white font-bold text-sm">
                  AA
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-800">American Airlines</div>
                  <div className="text-xs text-gray-500">noreply@aa.com</div>
                </div>
              </div>
              <div className="font-medium text-gray-900">{decision.message_subject}</div>
            </div>
            {/* Email body */}
            <div className="p-4">
              <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                {decision.message_body}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
