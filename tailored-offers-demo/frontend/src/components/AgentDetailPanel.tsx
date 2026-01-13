import type { AgentResult } from '../types';

interface AgentConfig {
  id: string;
  name: string;
  short_name: string;
  icon: string;
  description: string;
}

interface Props {
  agents: AgentConfig[];
  agentResults: Record<string, AgentResult>;
  selectedAgentTab: string | null;
  onSelectTab: (agentId: string) => void;
}

const icons: Record<string, string> = {
  brain: '🧠',
  chart: '📊',
  scale: '⚖️',
  sparkles: '✨',
  phone: '📱',
  trending: '📈',
};

// MCP Tools used by each agent (from existing systems)
const agentTools: Record<string, { tool: string; system: string }[]> = {
  customer_intelligence: [
    { tool: 'get_customer_profile', system: 'AADV DB' },
    { tool: 'get_suppression_status', system: 'CRM' },
  ],
  flight_optimization: [
    { tool: 'get_flight_inventory', system: 'DCSID' },
    { tool: 'get_pricing', system: 'RM Engine' },
  ],
  offer_orchestration: [
    { tool: 'get_propensity_scores', system: 'ML Model' },
    { tool: 'get_pricing', system: 'RM Engine' },
  ],
  personalization: [
    { tool: 'get_customer_profile', system: 'AADV DB' },
  ],
  channel_timing: [
    { tool: 'get_consent_status', system: 'Preferences DB' },
    { tool: 'get_engagement_history', system: 'Analytics' },
  ],
  measurement: [
    { tool: 'assign_experiment', system: 'Experiment Platform' },
  ],
};

export function AgentDetailPanel({ agents, agentResults, selectedAgentTab, onSelectTab }: Props) {
  const selectedResult = selectedAgentTab ? agentResults[selectedAgentTab] : null;
  const selectedAgent = agents.find(a => a.id === selectedAgentTab);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
        {agents.map((agent) => {
          const result = agentResults[agent.id];
          const hasResult = !!result;
          const isSelected = selectedAgentTab === agent.id;

          return (
            <button
              key={agent.id}
              onClick={() => onSelectTab(agent.id)}
              disabled={!hasResult}
              className={`
                flex items-center gap-2 px-4 py-3 text-sm font-medium
                border-b-2 transition-colors whitespace-nowrap
                ${isSelected
                  ? 'border-blue-500 text-blue-600 bg-white'
                  : hasResult
                    ? 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    : 'border-transparent text-gray-400 cursor-not-allowed'
                }
              `}
            >
              <span>{icons[agent.icon]}</span>
              <span>{agent.short_name}</span>
              {result?.status === 'complete' && (
                <span className="text-emerald-500">✓</span>
              )}
              {result?.status === 'skipped' && (
                <span className="text-amber-500">—</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="p-4">
        {!selectedResult ? (
          <div className="text-center text-gray-500 py-12">
            <p className="text-lg">Select an agent to view its reasoning</p>
            <p className="text-sm mt-1">Run an evaluation to see agent outputs</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">
                  {icons[selectedAgent?.icon || '']} {selectedResult.agent_name}
                </h3>
                <p className="text-sm text-gray-500">{selectedAgent?.description}</p>
              </div>
              <div className="text-right">
                <span className={`
                  px-3 py-1 rounded-full text-sm font-medium
                  ${selectedResult.status === 'complete' ? 'bg-emerald-100 text-emerald-700' : ''}
                  ${selectedResult.status === 'skipped' ? 'bg-amber-100 text-amber-700' : ''}
                `}>
                  {selectedResult.summary}
                </span>
                <div className="text-xs text-gray-400 mt-1">
                  {selectedResult.duration_ms}ms
                </div>
              </div>
            </div>

            {/* MCP Tools Used */}
            {selectedAgentTab && agentTools[selectedAgentTab] && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                <div className="text-xs font-semibold text-purple-700 uppercase tracking-wide mb-2">
                  🔧 MCP Tools Called (Existing Systems)
                </div>
                <div className="flex flex-wrap gap-2">
                  {agentTools[selectedAgentTab].map(({ tool, system }) => (
                    <span
                      key={tool}
                      className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono"
                    >
                      {tool}() → <span className="text-purple-500">{system}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Reasoning */}
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                🧠 Agent Reasoning (This is what differentiates from rule engine)
              </div>
              <div className="bg-slate-800 rounded-lg p-4 max-h-64 overflow-y-auto custom-scrollbar">
                <pre className="reasoning-display text-slate-100">
                  {selectedResult.reasoning || 'No reasoning available'}
                </pre>
              </div>
            </div>

            {/* Outputs */}
            {selectedResult.outputs && Object.keys(selectedResult.outputs).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Key Outputs</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(selectedResult.outputs).map(([key, value]) => {
                    if (value === null || value === undefined) return null;
                    const displayValue = typeof value === 'object'
                      ? JSON.stringify(value)
                      : String(value);
                    return (
                      <span
                        key={key}
                        className="px-3 py-1 bg-gray-100 rounded-full text-sm text-gray-700"
                      >
                        <span className="font-medium">{key}:</span>{' '}
                        <span className="text-gray-600">{displayValue.slice(0, 50)}</span>
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
