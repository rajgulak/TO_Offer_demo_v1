import { AgentNode } from './AgentNode';
import type { AgentResult, AgentStatus } from '../types';

interface AgentConfig {
  id: string;
  name: string;
  short_name: string;
  icon: string;
}

interface Props {
  agents: AgentConfig[];
  agentResults: Record<string, AgentResult>;
  currentAgentId: string | null;
  selectedAgentTab: string | null;
  onSelectAgent: (agentId: string) => void;
}

export function PipelineVisualization({
  agents,
  agentResults,
  currentAgentId,
  selectedAgentTab,
  onSelectAgent,
}: Props) {
  const getAgentStatus = (agentId: string): AgentStatus => {
    if (currentAgentId === agentId) return 'processing';
    const result = agentResults[agentId];
    if (!result) return 'pending';
    return result.status as AgentStatus;
  };

  const getAgentSummary = (agentId: string): string | undefined => {
    return agentResults[agentId]?.summary;
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-6 flex items-center gap-2">
        <span>Agent Pipeline</span>
        {currentAgentId && (
          <span className="text-sm font-normal text-blue-600 animate-pulse">
            Processing...
          </span>
        )}
      </h2>

      {/* Pipeline visualization */}
      <div className="relative">
        {/* Connection lines (SVG) */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 0 }}
        >
          {agents.slice(0, -1).map((agent, idx) => {
            const x1 = 60 + idx * 140 + 48;
            const x2 = 60 + (idx + 1) * 140;
            const y = 48;
            const isActive = getAgentStatus(agent.id) === 'complete' ||
                           getAgentStatus(agents[idx + 1].id) === 'processing';

            return (
              <line
                key={`line-${idx}`}
                x1={x1}
                y1={y}
                x2={x2}
                y2={y}
                className={`connection-line ${isActive ? 'active' : ''}`}
                stroke={isActive ? '#3b82f6' : '#d1d5db'}
                strokeWidth={isActive ? 3 : 2}
              />
            );
          })}
        </svg>

        {/* Agent nodes */}
        <div className="relative flex items-start justify-center gap-8 py-4" style={{ zIndex: 1 }}>
          {agents.map((agent, idx) => (
            <div key={agent.id} className="flex items-center">
              <AgentNode
                id={agent.id}
                name={agent.name}
                shortName={agent.short_name}
                icon={agent.icon}
                status={getAgentStatus(agent.id)}
                summary={getAgentSummary(agent.id)}
                isSelected={selectedAgentTab === agent.id}
                onClick={() => onSelectAgent(agent.id)}
                step={idx + 1}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-6 flex items-center justify-center gap-6 text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-gray-300"></span>
          <span>Pending</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-400 animate-pulse"></span>
          <span>Processing</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-emerald-400"></span>
          <span>Complete</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-amber-400"></span>
          <span>Skipped</span>
        </div>
      </div>
    </div>
  );
}
