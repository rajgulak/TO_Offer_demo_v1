import { useState } from 'react';

export type ExecutionMode = 'choreography' | 'planner-worker';

interface Props {
  executionMode: ExecutionMode;
  onExecutionModeChange: (mode: ExecutionMode) => void;
  hitlEnabled: boolean;
  onHitlEnabledChange: (enabled: boolean) => void;
}

export function DemoControls({
  executionMode,
  onExecutionModeChange,
  hitlEnabled,
  onHitlEnabledChange,
}: Props) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🎛️</span>
          <span className="font-semibold text-gray-800">Demo Controls</span>
          <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
            ADR-002 & ADR-008
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="p-4 grid grid-cols-2 gap-6">
          {/* Execution Mode */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium text-gray-700">Execution Pattern</span>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">ADR-002</span>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => onExecutionModeChange('choreography')}
                className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                  executionMode === 'choreography'
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span>⚡</span>
                  <span className="font-medium">Choreography</span>
                </div>
                <p className="text-xs text-left opacity-75">
                  Sequential flow, fast execution (~2-3s)
                </p>
              </button>

              <button
                onClick={() => onExecutionModeChange('planner-worker')}
                className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                  executionMode === 'planner-worker'
                    ? 'border-amber-500 bg-amber-50 text-amber-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span>🧠</span>
                  <span className="font-medium">Planner-Worker</span>
                </div>
                <p className="text-xs text-left opacity-75">
                  LLM planner, self-healing (~5-10s)
                </p>
              </button>
            </div>

            <p className="text-xs text-gray-500 mt-2">
              {executionMode === 'choreography'
                ? 'Each node knows its next step. Best for normal execution.'
                : 'Planner decides dynamically. Best for error recovery.'}
            </p>
          </div>

          {/* HITL Toggle */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium text-gray-700">Human-in-the-Loop</span>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">ADR-008</span>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => onHitlEnabledChange(false)}
                className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                  !hitlEnabled
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span>🤖</span>
                  <span className="font-medium">Auto-Approve</span>
                </div>
                <p className="text-xs text-left opacity-75">
                  All offers sent automatically
                </p>
              </button>

              <button
                onClick={() => onHitlEnabledChange(true)}
                className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                  hitlEnabled
                    ? 'border-purple-500 bg-purple-50 text-purple-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span>👤</span>
                  <span className="font-medium">HITL Enabled</span>
                </div>
                <p className="text-xs text-left opacity-75">
                  High-value offers need approval
                </p>
              </button>
            </div>

            <p className="text-xs text-gray-500 mt-2">
              {hitlEnabled
                ? 'Offers >$400 or VIP customers require human approval.'
                : 'All offers are delivered without human review.'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
