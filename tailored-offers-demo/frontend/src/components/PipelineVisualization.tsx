import { useState } from 'react';
import type { AgentResult, AgentStatus, ComponentType } from '../types';

interface AgentConfig {
  id: string;
  name: string;
  short_name: string;
  icon: string;
  component_type: ComponentType;
}

interface Props {
  agents: AgentConfig[];
  agentResults: Record<string, AgentResult>;
  currentAgentId: string | null;
  selectedAgentTab: string | null;
  onSelectAgent: (agentId: string) => void;
}

// State field mappings for each node
const NODE_STATE_FIELDS: Record<string, { inputs: string[]; outputs: string[] }> = {
  load_data: {
    inputs: ['pnr_locator'],
    outputs: ['customer_data', 'flight_data', 'reservation_data', 'ml_scores']
  },
  customer_intelligence: {
    inputs: ['customer_data', 'reservation_data', 'ml_scores'],
    outputs: ['customer_eligible', 'customer_segment', 'suppression_reason']
  },
  flight_optimization: {
    inputs: ['flight_data', 'reservation_data'],
    outputs: ['flight_priority', 'recommended_cabins', 'inventory_status']
  },
  offer_orchestration: {
    inputs: ['customer_segment', 'recommended_cabins', 'ml_scores', 'flight_data'],
    outputs: ['should_send_offer', 'selected_offer', 'offer_price', 'expected_value', 'fallback_offer']
  },
  personalization: {
    inputs: ['customer_data', 'selected_offer', 'offer_price', 'flight_data'],
    outputs: ['message_subject', 'message_body', 'message_tone']
  },
  channel_timing: {
    inputs: ['customer_data', 'reservation_data'],
    outputs: ['selected_channel', 'send_time', 'backup_channel']
  },
  measurement: {
    inputs: ['pnr_locator', 'selected_offer'],
    outputs: ['experiment_group', 'tracking_id']
  },
  final_decision: {
    inputs: ['should_send_offer', 'selected_offer', 'offer_price', 'message_subject', 'selected_channel', 'experiment_group'],
    outputs: ['final_decision']
  }
};

export function PipelineVisualization({
  agents: _agents,
  agentResults,
  currentAgentId,
  selectedAgentTab: _selectedAgentTab,
  onSelectAgent,
}: Props) {
  const [showStatePanel, setShowStatePanel] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const getAgentStatus = (agentId: string): AgentStatus => {
    if (currentAgentId === agentId) return 'processing';
    const result = agentResults[agentId];
    if (!result) return 'pending';
    return result.status as AgentStatus;
  };

  // Check if customer was eligible (to show conditional path)
  const customerEligible = agentResults['customer_intelligence']?.status === 'complete' &&
    !agentResults['customer_intelligence']?.summary?.includes('NOT ELIGIBLE');

  // Check if offer was made (to show conditional path)
  const offerMade = agentResults['offer_orchestration']?.status === 'complete' &&
    !agentResults['offer_orchestration']?.summary?.includes('NO OFFER');

  // Determine which path was taken
  const earlyExit = agentResults['customer_intelligence']?.status === 'complete' && !customerEligible;
  const offerExit = agentResults['offer_orchestration']?.status === 'complete' && !offerMade;

  // Get completed nodes for edge animation
  const completedNodes = Object.entries(agentResults)
    .filter(([, r]) => r.status === 'complete')
    .map(([id]) => id);

  // Extract actual state values from results
  const getStateValue = (key: string): string | null => {
    for (const result of Object.values(agentResults)) {
      if (result.outputs && key in result.outputs) {
        const val = result.outputs[key];
        if (typeof val === 'boolean') return val ? '✓ true' : '✗ false';
        if (typeof val === 'number') return val.toFixed(2);
        if (typeof val === 'string') return val.length > 20 ? val.slice(0, 20) + '...' : val;
        if (Array.isArray(val)) return `[${val.join(', ')}]`;
        return JSON.stringify(val).slice(0, 30);
      }
    }
    return null;
  };

  // Render animated edge with flowing particles
  const renderAnimatedEdge = (
    pathD: string,
    isActive: boolean,
    isError: boolean = false,
    key: string
  ) => {
    // Animation phase used for coordinating particle movement
    return (
      <g key={key}>
        <path
          d={pathD}
          fill="none"
          stroke={isError ? '#ef4444' : isActive ? '#10b981' : '#d1d5db'}
          strokeWidth={isActive ? 3 : 2}
          strokeDasharray={isError && !earlyExit && !offerExit ? '4' : '0'}
        />
        {isActive && !isError && (
          <>
            <circle r="4" fill="#10b981">
              <animateMotion dur="1.5s" repeatCount="indefinite" path={pathD} />
            </circle>
            <circle r="4" fill="#10b981" opacity="0.5">
              <animateMotion dur="1.5s" repeatCount="indefinite" path={pathD} begin="0.5s" />
            </circle>
          </>
        )}
      </g>
    );
  };

  // Node hover tooltip
  const renderNodeTooltip = (nodeId: string, x: number, y: number) => {
    if (hoveredNode !== nodeId) return null;
    const fields = NODE_STATE_FIELDS[nodeId];
    if (!fields) return null;

    return (
      <g transform={`translate(${x}, ${y})`}>
        <rect
          x="-100"
          y="-80"
          width="200"
          height="75"
          rx="6"
          fill="#1e293b"
          fillOpacity="0.95"
          stroke="#475569"
        />
        <text x="-90" y="-60" fontSize="8" fill="#94a3b8" fontWeight="bold">READS FROM STATE:</text>
        <text x="-90" y="-48" fontSize="7" fill="#60a5fa">{fields.inputs.slice(0, 3).join(', ')}</text>
        <text x="-90" y="-32" fontSize="8" fill="#94a3b8" fontWeight="bold">WRITES TO STATE:</text>
        <text x="-90" y="-20" fontSize="7" fill="#4ade80">{fields.outputs.slice(0, 3).join(', ')}</text>
      </g>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <span>LangGraph Workflow</span>
          <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
            Sequential + Conditional Routing
          </span>
          {currentAgentId && (
            <span className="text-sm font-normal text-blue-600 animate-pulse">
              Processing...
            </span>
          )}
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowStatePanel(!showStatePanel)}
            className={`text-xs px-3 py-1.5 rounded transition-colors ${
              showStatePanel
                ? 'bg-slate-700 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {showStatePanel ? '✓ State View' : '{ } View State'}
          </button>
        </div>
      </div>

      {/* LangGraph Code Reference */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-4 font-mono text-xs">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-slate-500"># workflow.py</span>
            <span className="text-slate-700 ml-2">
              <span className="text-purple-600">workflow</span> = StateGraph(<span className="text-blue-600">AgentState</span>)
            </span>
          </div>
          <div className="text-slate-400 text-[10px]">
            Pattern: Sequential Pipeline with Short-Circuit
          </div>
        </div>
      </div>

      {/* Graph Visualization */}
      <div className="relative bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg p-4 overflow-x-auto border border-slate-200">
        <svg className="w-full" height="340" viewBox="0 0 920 340">
          {/* Background Grid */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e2e8f0" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Entry Point */}
          <g transform="translate(25, 150)">
            <circle r="14" fill="#10b981" stroke="#059669" strokeWidth="2">
              <animate attributeName="r" values="14;16;14" dur="2s" repeatCount="indefinite" />
            </circle>
            <text x="0" y="5" textAnchor="middle" fontSize="11" fill="white" fontWeight="bold">▶</text>
            <text x="0" y="35" textAnchor="middle" fontSize="9" fill="#6b7280" fontWeight="500">START</text>
            <text x="0" y="46" textAnchor="middle" fontSize="7" fill="#94a3b8">entry_point</text>
          </g>

          {/* Edge: START → load_data */}
          {renderAnimatedEdge("M 39 150 L 75 150", true, false, "start-load")}

          {/* Node: load_data */}
          <g
            transform="translate(75, 115)"
            onMouseEnter={() => setHoveredNode('load_data')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="85"
              height="70"
              rx="8"
              fill="#f8fafc"
              stroke="#64748b"
              strokeWidth="2"
              className="transition-all hover:stroke-blue-500"
            />
            <text x="42" y="28" textAnchor="middle" fontSize="18">📥</text>
            <text x="42" y="45" textAnchor="middle" fontSize="9" fill="#475569" fontWeight="600">load_data</text>
            <text x="42" y="58" textAnchor="middle" fontSize="7" fill="#94a3b8">MCP Tools</text>
            {/* Type badge */}
            <rect x="55" y="5" width="26" height="14" rx="3" fill="#64748b" />
            <text x="68" y="15" textAnchor="middle" fontSize="7" fill="white">fn</text>
          </g>
          {renderNodeTooltip('load_data', 117, 115)}

          {/* Edge: load_data → customer_intelligence */}
          {renderAnimatedEdge(
            "M 160 150 L 190 150",
            completedNodes.includes('customer_intelligence') || currentAgentId === 'customer_intelligence',
            false,
            "load-customer"
          )}

          {/* Node: customer_intelligence */}
          <g
            transform="translate(190, 110)"
            onClick={() => onSelectAgent('customer_intelligence')}
            onMouseEnter={() => setHoveredNode('customer_intelligence')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="105"
              height="80"
              rx="10"
              fill={getAgentStatus('customer_intelligence') === 'complete' ? '#ecfdf5' :
                    getAgentStatus('customer_intelligence') === 'processing' ? '#dbeafe' : '#f8fafc'}
              stroke={getAgentStatus('customer_intelligence') === 'complete' ? '#10b981' :
                      getAgentStatus('customer_intelligence') === 'processing' ? '#3b82f6' : '#cbd5e1'}
              strokeWidth={getAgentStatus('customer_intelligence') === 'processing' ? 3 : 2}
              className={getAgentStatus('customer_intelligence') === 'processing' ? 'animate-pulse' : 'transition-all hover:stroke-blue-500'}
            />
            <text x="52" y="28" textAnchor="middle" fontSize="20">🧠</text>
            <text x="52" y="45" textAnchor="middle" fontSize="8" fill="#475569" fontWeight="700">customer_</text>
            <text x="52" y="56" textAnchor="middle" fontSize="8" fill="#475569" fontWeight="700">intelligence</text>
            {/* Status indicator */}
            {getAgentStatus('customer_intelligence') === 'complete' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#10b981" />
                <text x="90" y="19" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            {getAgentStatus('customer_intelligence') === 'processing' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#3b82f6">
                  <animate attributeName="opacity" values="1;0.5;1" dur="1s" repeatCount="indefinite" />
                </circle>
                <text x="90" y="19" textAnchor="middle" fontSize="8" fill="white">⚡</text>
              </g>
            )}
            {/* Type badge */}
            <rect x="5" y="62" width="45" height="14" rx="3" fill="#64748b" />
            <text x="27" y="72" textAnchor="middle" fontSize="6" fill="white">WORKFLOW</text>
          </g>
          {renderNodeTooltip('customer_intelligence', 242, 110)}

          {/* Conditional Diamond after customer_intelligence */}
          <g transform="translate(315, 133)">
            <polygon
              points="17,0 34,17 17,34 0,17"
              fill="#fef3c7"
              stroke="#f59e0b"
              strokeWidth="2"
            />
            <text x="17" y="21" textAnchor="middle" fontSize="12" fill="#92400e">?</text>
          </g>

          {/* Edge: customer_intelligence → diamond */}
          {renderAnimatedEdge(
            "M 295 150 L 315 150",
            completedNodes.includes('customer_intelligence'),
            false,
            "customer-diamond"
          )}

          {/* Edge: diamond → flight_optimization (eligible=true) */}
          {renderAnimatedEdge(
            "M 349 150 L 385 150",
            customerEligible && (completedNodes.includes('flight_optimization') || currentAgentId === 'flight_optimization'),
            false,
            "diamond-flight"
          )}
          <text x="365" y="142" textAnchor="middle" fontSize="7" fill="#16a34a" fontWeight="500">eligible</text>

          {/* Edge: diamond → END (eligible=false) - curved path down */}
          <path
            d="M 332 167 L 332 295 L 820 295"
            fill="none"
            stroke={earlyExit ? '#ef4444' : '#fecaca'}
            strokeWidth={earlyExit ? 3 : 2}
            strokeDasharray={earlyExit ? '0' : '6'}
            markerEnd="url(#arrowhead-red)"
          />
          {earlyExit && (
            <circle r="4" fill="#ef4444">
              <animateMotion dur="2s" repeatCount="indefinite" path="M 332 167 L 332 295 L 820 295" />
            </circle>
          )}
          <text x="332" y="220" textAnchor="middle" fontSize="7" fill="#dc2626" transform="rotate(-90, 332, 220)">suppressed/ineligible</text>

          {/* Node: flight_optimization */}
          <g
            transform="translate(385, 110)"
            onClick={() => onSelectAgent('flight_optimization')}
            onMouseEnter={() => setHoveredNode('flight_optimization')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="105"
              height="80"
              rx="10"
              fill={getAgentStatus('flight_optimization') === 'complete' ? '#ecfdf5' :
                    getAgentStatus('flight_optimization') === 'processing' ? '#dbeafe' : '#f8fafc'}
              stroke={getAgentStatus('flight_optimization') === 'complete' ? '#10b981' :
                      getAgentStatus('flight_optimization') === 'processing' ? '#3b82f6' : '#cbd5e1'}
              strokeWidth={getAgentStatus('flight_optimization') === 'processing' ? 3 : 2}
              className={getAgentStatus('flight_optimization') === 'processing' ? 'animate-pulse' : 'transition-all hover:stroke-blue-500'}
            />
            <text x="52" y="28" textAnchor="middle" fontSize="20">📊</text>
            <text x="52" y="45" textAnchor="middle" fontSize="8" fill="#475569" fontWeight="700">flight_</text>
            <text x="52" y="56" textAnchor="middle" fontSize="8" fill="#475569" fontWeight="700">optimization</text>
            {getAgentStatus('flight_optimization') === 'complete' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#10b981" />
                <text x="90" y="19" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            {getAgentStatus('flight_optimization') === 'processing' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#3b82f6">
                  <animate attributeName="opacity" values="1;0.5;1" dur="1s" repeatCount="indefinite" />
                </circle>
                <text x="90" y="19" textAnchor="middle" fontSize="8" fill="white">⚡</text>
              </g>
            )}
            <rect x="5" y="62" width="45" height="14" rx="3" fill="#64748b" />
            <text x="27" y="72" textAnchor="middle" fontSize="6" fill="white">WORKFLOW</text>
          </g>
          {renderNodeTooltip('flight_optimization', 437, 110)}

          {/* Edge: flight_optimization → offer_orchestration */}
          {renderAnimatedEdge(
            "M 490 150 L 520 150",
            completedNodes.includes('offer_orchestration') || currentAgentId === 'offer_orchestration',
            false,
            "flight-offer"
          )}

          {/* Node: offer_orchestration (THE AGENT - highlighted) */}
          <g
            transform="translate(520, 100)"
            onClick={() => onSelectAgent('offer_orchestration')}
            onMouseEnter={() => setHoveredNode('offer_orchestration')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            {/* Glow effect for agent */}
            <rect
              width="115"
              height="100"
              rx="12"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="1"
              opacity="0.3"
              transform="translate(-5, -5)"
            >
              <animate attributeName="opacity" values="0.3;0.6;0.3" dur="2s" repeatCount="indefinite" />
            </rect>
            <rect
              width="105"
              height="90"
              rx="10"
              fill={getAgentStatus('offer_orchestration') === 'complete' ? '#eff6ff' :
                    getAgentStatus('offer_orchestration') === 'processing' ? '#dbeafe' : '#f0f9ff'}
              stroke={getAgentStatus('offer_orchestration') === 'complete' ? '#3b82f6' :
                      getAgentStatus('offer_orchestration') === 'processing' ? '#2563eb' : '#60a5fa'}
              strokeWidth="3"
              className={getAgentStatus('offer_orchestration') === 'processing' ? 'animate-pulse' : ''}
            />
            <text x="52" y="30" textAnchor="middle" fontSize="22">⚖️</text>
            <text x="52" y="50" textAnchor="middle" fontSize="8" fill="#1e40af" fontWeight="700">offer_</text>
            <text x="52" y="61" textAnchor="middle" fontSize="8" fill="#1e40af" fontWeight="700">orchestration</text>
            {getAgentStatus('offer_orchestration') === 'complete' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#3b82f6" />
                <text x="90" y="19" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            {getAgentStatus('offer_orchestration') === 'processing' && (
              <g>
                <circle cx="90" cy="15" r="10" fill="#2563eb">
                  <animate attributeName="opacity" values="1;0.5;1" dur="0.8s" repeatCount="indefinite" />
                </circle>
                <text x="90" y="19" textAnchor="middle" fontSize="8" fill="white">🧠</text>
              </g>
            )}
            {/* Agent badge */}
            <rect x="5" y="72" width="50" height="14" rx="3" fill="#2563eb" />
            <text x="30" y="82" textAnchor="middle" fontSize="6" fill="white" fontWeight="bold">🧠 AGENT</text>
            <text x="70" y="82" textAnchor="middle" fontSize="6" fill="#3b82f6">+LLM</text>
          </g>
          {renderNodeTooltip('offer_orchestration', 572, 100)}

          {/* Conditional Diamond after offer_orchestration */}
          <g transform="translate(645, 133)">
            <polygon
              points="17,0 34,17 17,34 0,17"
              fill="#fef3c7"
              stroke="#f59e0b"
              strokeWidth="2"
            />
            <text x="17" y="21" textAnchor="middle" fontSize="12" fill="#92400e">?</text>
          </g>

          {/* Edge: offer_orchestration → diamond */}
          {renderAnimatedEdge(
            "M 625 150 L 645 150",
            completedNodes.includes('offer_orchestration'),
            false,
            "offer-diamond"
          )}

          {/* Edge: diamond → personalization (should_send=true) */}
          <path
            d="M 679 150 L 720 150 L 720 60 L 755 60"
            fill="none"
            stroke={offerMade ? '#10b981' : '#d1d5db'}
            strokeWidth={offerMade ? 3 : 2}
            markerEnd="url(#arrowhead)"
          />
          {offerMade && (
            <circle r="4" fill="#10b981">
              <animateMotion dur="1.2s" repeatCount="indefinite" path="M 679 150 L 720 150 L 720 60 L 755 60" />
            </circle>
          )}
          <text x="700" y="105" textAnchor="middle" fontSize="7" fill="#16a34a" transform="rotate(-90, 700, 105)">send_offer</text>

          {/* Edge: diamond → END (should_send=false) */}
          <path
            d="M 662 167 L 662 295 L 820 295"
            fill="none"
            stroke={offerExit ? '#ef4444' : '#fecaca'}
            strokeWidth={offerExit ? 3 : 2}
            strokeDasharray={offerExit ? '0' : '6'}
            markerEnd="url(#arrowhead-red)"
          />
          {offerExit && (
            <circle r="4" fill="#ef4444">
              <animateMotion dur="2s" repeatCount="indefinite" path="M 662 167 L 662 295 L 820 295" />
            </circle>
          )}
          <text x="662" y="220" textAnchor="middle" fontSize="7" fill="#dc2626" transform="rotate(-90, 662, 220)">no_offer</text>

          {/* Node: personalization (LLM Call) */}
          <g
            transform="translate(755, 25)"
            onClick={() => onSelectAgent('personalization')}
            onMouseEnter={() => setHoveredNode('personalization')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="95"
              height="70"
              rx="10"
              fill={getAgentStatus('personalization') === 'complete' ? '#faf5ff' :
                    getAgentStatus('personalization') === 'processing' ? '#f3e8ff' : '#fdf4ff'}
              stroke={getAgentStatus('personalization') === 'complete' ? '#a855f7' :
                      getAgentStatus('personalization') === 'processing' ? '#9333ea' : '#d8b4fe'}
              strokeWidth={getAgentStatus('personalization') === 'processing' ? 3 : 2}
              className={getAgentStatus('personalization') === 'processing' ? 'animate-pulse' : 'transition-all hover:stroke-purple-500'}
            />
            <text x="47" y="28" textAnchor="middle" fontSize="18">✨</text>
            <text x="47" y="46" textAnchor="middle" fontSize="8" fill="#7c3aed" fontWeight="700">personalization</text>
            {getAgentStatus('personalization') === 'complete' && (
              <g>
                <circle cx="82" cy="12" r="10" fill="#a855f7" />
                <text x="82" y="16" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            {getAgentStatus('personalization') === 'processing' && (
              <g>
                <circle cx="82" cy="12" r="10" fill="#9333ea">
                  <animate attributeName="opacity" values="1;0.5;1" dur="0.8s" repeatCount="indefinite" />
                </circle>
                <text x="82" y="16" textAnchor="middle" fontSize="8" fill="white">✨</text>
              </g>
            )}
            <rect x="5" y="52" width="42" height="14" rx="3" fill="#9333ea" />
            <text x="26" y="62" textAnchor="middle" fontSize="6" fill="white">LLM CALL</text>
          </g>
          {renderNodeTooltip('personalization', 802, 25)}

          {/* Edge: personalization → channel_timing */}
          {renderAnimatedEdge(
            "M 802 95 L 802 120",
            completedNodes.includes('channel_timing') || currentAgentId === 'channel_timing',
            false,
            "personal-channel"
          )}

          {/* Node: channel_timing */}
          <g
            transform="translate(755, 120)"
            onClick={() => onSelectAgent('channel_timing')}
            onMouseEnter={() => setHoveredNode('channel_timing')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="95"
              height="65"
              rx="10"
              fill={getAgentStatus('channel_timing') === 'complete' ? '#ecfdf5' :
                    getAgentStatus('channel_timing') === 'processing' ? '#dbeafe' : '#f8fafc'}
              stroke={getAgentStatus('channel_timing') === 'complete' ? '#10b981' :
                      getAgentStatus('channel_timing') === 'processing' ? '#3b82f6' : '#cbd5e1'}
              strokeWidth={getAgentStatus('channel_timing') === 'processing' ? 3 : 2}
              className={getAgentStatus('channel_timing') === 'processing' ? 'animate-pulse' : 'transition-all hover:stroke-blue-500'}
            />
            <text x="47" y="26" textAnchor="middle" fontSize="18">📱</text>
            <text x="47" y="44" textAnchor="middle" fontSize="8" fill="#475569" fontWeight="700">channel_timing</text>
            {getAgentStatus('channel_timing') === 'complete' && (
              <g>
                <circle cx="82" cy="12" r="10" fill="#10b981" />
                <text x="82" y="16" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            <rect x="5" y="48" width="45" height="14" rx="3" fill="#64748b" />
            <text x="27" y="58" textAnchor="middle" fontSize="6" fill="white">WORKFLOW</text>
          </g>

          {/* Edge: channel_timing → measurement */}
          {renderAnimatedEdge(
            "M 802 185 L 802 205",
            completedNodes.includes('measurement') || currentAgentId === 'measurement',
            false,
            "channel-measure"
          )}

          {/* Node: measurement (Tracking Setup - Post-Decision) */}
          <g
            transform="translate(755, 205)"
            onClick={() => onSelectAgent('measurement')}
            onMouseEnter={() => setHoveredNode('measurement')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
          >
            {/* Dashed border to indicate post-decision */}
            <rect
              width="95"
              height="60"
              rx="10"
              fill={getAgentStatus('measurement') === 'complete' ? '#fefce8' :
                    getAgentStatus('measurement') === 'processing' ? '#fef9c3' : '#fefce8'}
              stroke={getAgentStatus('measurement') === 'complete' ? '#ca8a04' :
                      getAgentStatus('measurement') === 'processing' ? '#eab308' : '#d4d4d8'}
              strokeWidth="2"
              strokeDasharray="4 2"
              className={getAgentStatus('measurement') === 'processing' ? 'animate-pulse' : 'transition-all hover:stroke-yellow-500'}
            />
            <text x="47" y="25" textAnchor="middle" fontSize="18">🏷️</text>
            <text x="47" y="42" textAnchor="middle" fontSize="8" fill="#854d0e" fontWeight="700">tracking_setup</text>
            {getAgentStatus('measurement') === 'complete' && (
              <g>
                <circle cx="82" cy="12" r="10" fill="#ca8a04" />
                <text x="82" y="16" textAnchor="middle" fontSize="10" fill="white">✓</text>
              </g>
            )}
            <rect x="5" y="45" width="55" height="12" rx="3" fill="#ca8a04" />
            <text x="32" y="54" textAnchor="middle" fontSize="6" fill="white">POST-DECISION</text>
          </g>

          {/* Edge: measurement → final_decision */}
          {renderAnimatedEdge(
            "M 802 265 L 802 280",
            agentResults['measurement']?.status === 'complete',
            false,
            "measure-final"
          )}

          {/* Node: final_decision */}
          <g transform="translate(755, 280)">
            <rect
              width="95"
              height="50"
              rx="10"
              fill="#f0fdf4"
              stroke="#22c55e"
              strokeWidth="2"
            />
            <text x="47" y="24" textAnchor="middle" fontSize="16">🎯</text>
            <text x="47" y="40" textAnchor="middle" fontSize="8" fill="#166534" fontWeight="700">final_decision</text>
          </g>

          {/* Edge: final_decision → END */}
          <line x1="850" y1="305" x2="880" y2="305" stroke="#22c55e" strokeWidth="2" markerEnd="url(#arrowhead-green)" />

          {/* END Node */}
          <g transform="translate(880, 290)">
            <circle r="15" cx="15" cy="15" fill="#dc2626" stroke="#b91c1c" strokeWidth="2" />
            <rect x="8" y="10" width="14" height="10" fill="white" rx="1" />
            <text x="15" y="42" textAnchor="middle" fontSize="9" fill="#6b7280" fontWeight="500">END</text>
          </g>

          {/* Arrow markers */}
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
            </marker>
            <marker id="arrowhead-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#ef4444" />
            </marker>
            <marker id="arrowhead-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#22c55e" />
            </marker>
          </defs>
        </svg>

        {/* Legend */}
        <div className="flex items-center justify-center gap-4 mt-4 text-xs text-gray-600 flex-wrap border-t border-slate-200 pt-4">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-slate-100 border-2 border-slate-500 flex items-center justify-center text-[8px]">⚡</div>
            <span>Workflow (4)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-blue-100 border-2 border-blue-500 flex items-center justify-center text-[8px]">🧠</div>
            <span>Agent (1)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-purple-100 border-2 border-purple-500 flex items-center justify-center text-[8px]">✨</div>
            <span>LLM Call (1)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-yellow-100 border-2 border-yellow-600 border-dashed flex items-center justify-center text-[8px]">🏷️</div>
            <span>Post-Decision</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-4 rotate-45 bg-amber-200 border border-amber-500"></div>
            <span>Conditional</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-green-500"></div>
            <span>Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-red-400 border-dashed border-t-2 border-red-400"></div>
            <span>Exit</span>
          </div>
        </div>
      </div>

      {/* Live State Panel */}
      {showStatePanel && (
        <div className="mt-4 bg-slate-900 rounded-lg p-4 font-mono text-xs overflow-x-auto">
          <div className="flex justify-between items-center mb-3">
            <div className="text-slate-400">
              <span className="text-blue-400">class</span>{' '}
              <span className="text-yellow-400">AgentState</span>
              <span className="text-slate-500">(TypedDict)</span>
              <span className="text-slate-600 ml-2">— Live values from workflow execution</span>
            </div>
            <div className="text-[10px] text-slate-500 bg-slate-800 px-2 py-1 rounded">
              {Object.keys(agentResults).length > 0 ? `${Object.keys(agentResults).length} nodes completed` : 'Waiting for execution...'}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {/* Input State */}
            <div className="bg-slate-800 rounded-lg p-3">
              <div className="text-slate-500 text-[10px] uppercase tracking-wide mb-2">📥 Input State</div>
              <div className="space-y-1 text-slate-300">
                <div className="flex justify-between">
                  <span>pnr_locator:</span>
                  <span className="text-emerald-400">{getStateValue('pnr_locator') || '"ABC123"'}</span>
                </div>
                <div className="flex justify-between">
                  <span>customer_data:</span>
                  <span className="text-blue-400">{Object.keys(agentResults).length > 0 ? '{ ... }' : 'None'}</span>
                </div>
                <div className="flex justify-between">
                  <span>flight_data:</span>
                  <span className="text-blue-400">{Object.keys(agentResults).length > 0 ? '{ ... }' : 'None'}</span>
                </div>
                <div className="flex justify-between">
                  <span>ml_scores:</span>
                  <span className="text-blue-400">{Object.keys(agentResults).length > 0 ? '{ ... }' : 'None'}</span>
                </div>
              </div>
            </div>

            {/* Control Flow State */}
            <div className="bg-slate-800 rounded-lg p-3">
              <div className="text-slate-500 text-[10px] uppercase tracking-wide mb-2">🔀 Control Flow</div>
              <div className="space-y-1 text-slate-300">
                <div className="flex justify-between">
                  <span>customer_eligible:</span>
                  <span className={customerEligible ? 'text-emerald-400' : earlyExit ? 'text-red-400' : 'text-slate-500'}>
                    {agentResults['customer_intelligence'] ? (customerEligible ? 'true' : 'false') : 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>should_send_offer:</span>
                  <span className={offerMade ? 'text-emerald-400' : offerExit ? 'text-red-400' : 'text-slate-500'}>
                    {agentResults['offer_orchestration'] ? (offerMade ? 'true' : 'false') : 'None'}
                  </span>
                </div>
              </div>
            </div>

            {/* Agent Outputs */}
            <div className="bg-slate-800 rounded-lg p-3">
              <div className="text-slate-500 text-[10px] uppercase tracking-wide mb-2">📤 Agent Outputs</div>
              <div className="space-y-1 text-slate-300">
                <div className="flex justify-between">
                  <span>customer_segment:</span>
                  <span className="text-amber-400">
                    {agentResults['customer_intelligence']?.outputs?.customer_segment || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>selected_offer:</span>
                  <span className="text-amber-400">
                    {agentResults['offer_orchestration']?.outputs?.selected_offer || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>offer_price:</span>
                  <span className="text-amber-400">
                    {agentResults['offer_orchestration']?.outputs?.offer_price ?
                      `$${agentResults['offer_orchestration'].outputs.offer_price}` : 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>expected_value:</span>
                  <span className="text-amber-400">
                    {agentResults['offer_orchestration']?.outputs?.expected_value ?
                      `$${agentResults['offer_orchestration'].outputs.expected_value?.toFixed(2)}` : 'None'}
                  </span>
                </div>
              </div>
            </div>

            {/* Delivery State */}
            <div className="bg-slate-800 rounded-lg p-3">
              <div className="text-slate-500 text-[10px] uppercase tracking-wide mb-2">📬 Delivery State</div>
              <div className="space-y-1 text-slate-300">
                <div className="flex justify-between">
                  <span>selected_channel:</span>
                  <span className="text-cyan-400">
                    {agentResults['channel_timing']?.outputs?.selected_channel || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>send_time:</span>
                  <span className="text-cyan-400">
                    {agentResults['channel_timing']?.outputs?.send_time || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>experiment_group:</span>
                  <span className="text-cyan-400">
                    {agentResults['measurement']?.outputs?.experiment_group || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>tracking_id:</span>
                  <span className="text-cyan-400 text-[10px]">
                    {agentResults['measurement']?.outputs?.tracking_id || 'None'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning Trace */}
          <div className="mt-4 pt-3 border-t border-slate-700">
            <div className="text-slate-500 text-[10px] uppercase tracking-wide mb-2">📝 Reasoning Trace (accumulated)</div>
            <div className="bg-slate-950 rounded p-2 max-h-24 overflow-y-auto">
              {Object.values(agentResults).length === 0 ? (
                <div className="text-slate-600 italic">No trace yet - run evaluation to see agent reasoning</div>
              ) : (
                Object.entries(agentResults).map(([id, result]) => (
                  <div key={id} className="text-slate-400 text-[10px] mb-1">
                    <span className="text-blue-400">[{id}]</span> {result.summary}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edge Definitions Code */}
      <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3 font-mono text-xs">
        <div className="flex justify-between items-center mb-2">
          <span className="text-slate-500"># Graph edges from workflow.py</span>
          <span className="text-[10px] text-slate-400">LangGraph StateGraph</span>
        </div>
        <div className="grid md:grid-cols-2 gap-x-6 gap-y-1 text-slate-700">
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"load_data"</span>
            <span className="text-slate-400">→</span>
            <span className="text-emerald-600">"customer_intelligence"</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"flight_optimization"</span>
            <span className="text-slate-400">→</span>
            <span className="text-emerald-600">"offer_orchestration"</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"personalization"</span>
            <span className="text-slate-400">→</span>
            <span className="text-emerald-600">"channel_timing"</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"channel_timing"</span>
            <span className="text-slate-400">→</span>
            <span className="text-emerald-600">"measurement"</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"measurement"</span>
            <span className="text-slate-400">→</span>
            <span className="text-emerald-600">"final_decision"</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-600">"final_decision"</span>
            <span className="text-slate-400">→</span>
            <span className="text-amber-600">END</span>
          </div>
        </div>
        <div className="mt-3 pt-2 border-t border-slate-300">
          <div className="text-slate-500 mb-1"># Conditional edges (short-circuit)</div>
          <div className="text-[11px] space-y-1">
            <div>
              <span className="text-purple-600">add_conditional_edges</span>
              (<span className="text-emerald-600">"customer_intelligence"</span>,
              <span className="text-blue-600 ml-1">should_continue_after_customer</span>)
              <span className="text-slate-400 ml-2">→ "flight_optimization" | "final_decision"</span>
            </div>
            <div>
              <span className="text-purple-600">add_conditional_edges</span>
              (<span className="text-emerald-600">"offer_orchestration"</span>,
              <span className="text-blue-600 ml-1">should_continue_after_offer</span>)
              <span className="text-slate-400 ml-2">→ "personalization" | "final_decision"</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
