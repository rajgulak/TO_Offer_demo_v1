import { useState } from 'react';

export function ArchitectureOverview() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl shadow-lg text-white overflow-hidden">
      {/* Collapsed Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-4">
          <span className="text-2xl">🏗️</span>
          <div className="text-left">
            <h2 className="font-semibold">MVP1 Architecture: Agents + Existing Systems</h2>
            <p className="text-sm text-slate-300">
              Agents reason over data from existing systems via MCP Tools — no system changes required
            </p>
          </div>
        </div>
        <span className={`text-xl transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-6 pb-6 space-y-6">
          {/* Architecture Diagram */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-center text-sm text-slate-400 mb-4">Data Flow Architecture</div>
            <div className="flex items-center justify-center gap-2 text-sm">
              <div className="bg-blue-600 px-3 py-2 rounded-lg text-center">
                <div className="font-bold">Agents</div>
                <div className="text-xs opacity-80">Reasoning Layer</div>
              </div>
              <span className="text-2xl">→</span>
              <div className="bg-purple-600 px-3 py-2 rounded-lg text-center">
                <div className="font-bold">MCP Tools</div>
                <div className="text-xs opacity-80">Standard Interface</div>
              </div>
              <span className="text-2xl">→</span>
              <div className="bg-emerald-600 px-3 py-2 rounded-lg text-center">
                <div className="font-bold">Existing Systems</div>
                <div className="text-xs opacity-80">Unchanged</div>
              </div>
            </div>
          </div>

          {/* Data Sources */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">📊 Data Sources (via MCP Tools)</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { name: 'Customer 360', system: 'AADV DB', icon: '👤' },
                { name: 'ML Scores', system: 'P(buy) Model', icon: '🤖' },
                { name: 'Inventory', system: 'DCSID', icon: '✈️' },
                { name: 'Pricing', system: 'RM Engine', icon: '💰' },
              ].map((source) => (
                <div key={source.name} className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-xl mb-1">{source.icon}</div>
                  <div className="text-sm font-medium">{source.name}</div>
                  <div className="text-xs text-slate-400">{source.system}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Agent vs Rule Engine Comparison */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🧠 Why Agents? (vs Rule Engine / Workflow)</h3>
            <div className="grid md:grid-cols-2 gap-4">
              {/* Rule Engine */}
              <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">⚙️</span>
                  <span className="font-semibold">Traditional Rule Engine</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span><code className="bg-slate-800 px-1 rounded">if P(buy) &gt; 0.5: send_offer()</code></span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Fixed thresholds, no context awareness</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Can't explain WHY a decision was made</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Breaks on edge cases</span>
                  </li>
                </ul>
              </div>

              {/* Agent Reasoning */}
              <div className="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">🧠</span>
                  <span className="font-semibold">Agent Reasoning</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>"Business EV ($122) &gt; MCE EV ($29), lead with Business"</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Considers inventory, timing, customer history</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Full explainability and audit trail</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Graceful fallbacks for edge cases</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Key Message */}
          <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg p-4 text-center">
            <div className="text-lg font-semibold mb-1">
              💡 ML gives you a score. Agents give you decisions + explanations.
            </div>
            <div className="text-sm text-slate-300">
              Same P(buy) = 0.73 → Different optimal actions for different customers
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
