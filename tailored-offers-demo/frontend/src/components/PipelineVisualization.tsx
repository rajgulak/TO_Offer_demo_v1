import { useState } from 'react';
import type { AgentResult, AgentStatus } from '../types';

interface Props {
  agentResults: Record<string, AgentResult>;
  currentAgentId: string | null;
  onSelectAgent: (agentId: string) => void;
  hitlEnabled?: boolean;
}

// Map old agent IDs to new phases for compatibility
const AGENT_TO_PHASE: Record<string, string> = {
  'customer_intelligence': 'prechecks',
  'flight_optimization': 'prechecks',
  'offer_orchestration': 'offer_agent',
  'personalization': 'delivery',
  'channel_timing': 'delivery',
  'measurement': 'delivery',
};

export function PipelineVisualization({
  agentResults,
  currentAgentId,
  onSelectAgent,
  hitlEnabled = false,
}: Props) {
  const [showStatePanel, setShowStatePanel] = useState(false);
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);

  // Get phase status based on agent results
  const getPhaseStatus = (phaseId: string): AgentStatus => {
    const phaseAgents = Object.entries(AGENT_TO_PHASE)
      .filter(([, phase]) => phase === phaseId)
      .map(([agentId]) => agentId);

    // Check if any agent in this phase is currently processing
    if (phaseAgents.includes(currentAgentId || '')) return 'processing';

    // Check if all agents in this phase are complete
    const results = phaseAgents.map(id => agentResults[id]);
    const allComplete = results.every(r => r?.status === 'complete');
    const anyComplete = results.some(r => r?.status === 'complete');

    if (allComplete) return 'complete';
    if (anyComplete) return 'processing';
    return 'pending';
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

  // Phase definitions for the new 3-phase architecture
  const phases = [
    {
      id: 'prechecks',
      name: 'Pre-checks',
      shortName: 'Pre-checks',
      icon: '🔍',
      type: 'workflow',
      description: 'Eligibility & Inventory validation',
      subSteps: [
        { id: 'customer_intelligence', name: 'Customer Eligibility', icon: '👤' },
        { id: 'flight_optimization', name: 'Inventory Check', icon: '📊' },
      ],
    },
    {
      id: 'offer_agent',
      name: 'Offer Agent',
      shortName: 'Offer Agent',
      icon: '🧠',
      type: 'agent',
      description: 'ReWOO: Planner → Worker → Solver',
      subSteps: [
        { id: 'offer_orchestration', name: 'ReWOO Decision', icon: '⚖️' },
      ],
    },
    {
      id: 'delivery',
      name: 'Delivery',
      shortName: 'Delivery',
      icon: '📬',
      type: 'workflow',
      description: 'Message, Channel & Tracking',
      subSteps: [
        { id: 'personalization', name: 'Message Generation', icon: '✨' },
        { id: 'channel_timing', name: 'Channel Selection', icon: '📱' },
        { id: 'measurement', name: 'Tracking Setup', icon: '🏷️' },
      ],
    },
  ];

  // Handle phase selection
  const handlePhaseClick = (phaseId: string) => {
    setSelectedPhase(selectedPhase === phaseId ? null : phaseId);
    // Select the first agent in the phase
    const phase = phases.find(p => p.id === phaseId);
    if (phase && phase.subSteps.length > 0) {
      onSelectAgent(phase.subSteps[0].id);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <span>Tailored Offers Pipeline</span>
          <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
            3-Phase Architecture
          </span>
          {hitlEnabled && (
            <span className="text-xs font-normal bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
              👤 HITL
            </span>
          )}
          {currentAgentId && (
            <span className="text-sm font-normal text-blue-600 animate-pulse">
              Processing...
            </span>
          )}
        </h2>
        <button
          onClick={() => setShowStatePanel(!showStatePanel)}
          className={`text-xs px-3 py-1.5 rounded transition-colors ${
            showStatePanel
              ? 'bg-slate-700 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          {showStatePanel ? '✓ Details' : 'View Details'}
        </button>
      </div>

      {/* Pipeline Visualization - Clean 3-Phase View */}
      <div className="relative bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg p-6 border border-slate-200">
        <svg className="w-full" height="200" viewBox="0 0 800 200">
          {/* Background Grid */}
          <defs>
            <pattern id="grid-3phase" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e2e8f0" strokeWidth="0.5" />
            </pattern>
            <marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#10b981" />
            </marker>
            <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
            </marker>
            <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#ef4444" />
            </marker>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-3phase)" />

          {/* START Node */}
          <g transform="translate(30, 100)">
            <circle r="18" fill="#10b981" stroke="#059669" strokeWidth="2">
              <animate attributeName="r" values="18;20;18" dur="2s" repeatCount="indefinite" />
            </circle>
            <text x="0" y="5" textAnchor="middle" fontSize="14" fill="white" fontWeight="bold">▶</text>
            <text x="0" y="40" textAnchor="middle" fontSize="10" fill="#6b7280">START</text>
          </g>

          {/* Arrow: START → Pre-checks */}
          <line x1="48" y1="100" x2="100" y2="100" stroke="#10b981" strokeWidth="2" markerEnd="url(#arrow-green)" />

          {/* Phase 1: Pre-checks */}
          <g
            transform="translate(100, 50)"
            onClick={() => handlePhaseClick('prechecks')}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="180"
              height="100"
              rx="12"
              fill={getPhaseStatus('prechecks') === 'complete' ? '#ecfdf5' :
                    getPhaseStatus('prechecks') === 'processing' ? '#dbeafe' : '#f8fafc'}
              stroke={getPhaseStatus('prechecks') === 'complete' ? '#10b981' :
                      getPhaseStatus('prechecks') === 'processing' ? '#3b82f6' : '#cbd5e1'}
              strokeWidth={getPhaseStatus('prechecks') === 'processing' ? 3 : 2}
              className={getPhaseStatus('prechecks') === 'processing' ? 'animate-pulse' : ''}
            />
            <text x="90" y="35" textAnchor="middle" fontSize="28">🔍</text>
            <text x="90" y="58" textAnchor="middle" fontSize="12" fill="#374151" fontWeight="700">Pre-checks</text>
            <rect x="45" y="68" width="90" height="18" rx="4" fill="#64748b" />
            <text x="90" y="81" textAnchor="middle" fontSize="9" fill="white">WORKFLOW</text>
            {getPhaseStatus('prechecks') === 'complete' && (
              <g>
                <circle cx="165" cy="15" r="12" fill="#10b981" />
                <text x="165" y="20" textAnchor="middle" fontSize="12" fill="white">✓</text>
              </g>
            )}
          </g>

          {/* Conditional Diamond after Pre-checks */}
          <g transform="translate(300, 83)">
            <polygon
              points="17,0 34,17 17,34 0,17"
              fill="#fef3c7"
              stroke="#f59e0b"
              strokeWidth="2"
            />
            <text x="17" y="21" textAnchor="middle" fontSize="12" fill="#92400e">?</text>
          </g>

          {/* Arrow: Pre-checks → Diamond */}
          <line x1="280" y1="100" x2="300" y2="100" stroke={getPhaseStatus('prechecks') === 'complete' ? '#10b981' : '#cbd5e1'} strokeWidth="2" />

          {/* Arrow: Diamond → Offer Agent (eligible) */}
          <line x1="334" y1="100" x2="380" y2="100" stroke={customerEligible ? '#10b981' : '#cbd5e1'} strokeWidth="2" markerEnd="url(#arrow-green)" />
          <text x="357" y="92" textAnchor="middle" fontSize="8" fill="#16a34a">eligible</text>

          {/* Exit path for ineligible */}
          {earlyExit && (
            <g>
              <path
                d="M 317 117 L 317 170 L 720 170"
                fill="none"
                stroke="#ef4444"
                strokeWidth="2"
                markerEnd="url(#arrow-red)"
              />
              <text x="450" y="185" textAnchor="middle" fontSize="9" fill="#dc2626">NOT ELIGIBLE - Skip to END</text>
            </g>
          )}

          {/* Phase 2: Offer Agent */}
          <g
            transform="translate(380, 40)"
            onClick={() => handlePhaseClick('offer_agent')}
            style={{ cursor: 'pointer' }}
          >
            {/* Glow effect for the agent */}
            <rect
              width="160"
              height="120"
              rx="14"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="1"
              opacity="0.3"
              transform="translate(-5, -5)"
            >
              <animate attributeName="opacity" values="0.3;0.6;0.3" dur="2s" repeatCount="indefinite" />
            </rect>
            <rect
              width="150"
              height="110"
              rx="12"
              fill={getPhaseStatus('offer_agent') === 'complete' ? '#eff6ff' :
                    getPhaseStatus('offer_agent') === 'processing' ? '#dbeafe' : '#f0f9ff'}
              stroke={getPhaseStatus('offer_agent') === 'complete' ? '#3b82f6' :
                      getPhaseStatus('offer_agent') === 'processing' ? '#2563eb' : '#60a5fa'}
              strokeWidth="3"
              className={getPhaseStatus('offer_agent') === 'processing' ? 'animate-pulse' : ''}
            />
            <text x="75" y="35" textAnchor="middle" fontSize="28">🧠</text>
            <text x="75" y="58" textAnchor="middle" fontSize="12" fill="#1e40af" fontWeight="700">Offer Agent</text>
            {/* ReWOO badge */}
            <rect x="20" y="68" width="110" height="20" rx="4" fill="#2563eb" />
            <text x="75" y="82" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">🎯 ReWOO Pattern</text>
            <text x="75" y="102" textAnchor="middle" fontSize="7" fill="#3b82f6">P → W → S</text>
            {getPhaseStatus('offer_agent') === 'complete' && (
              <g>
                <circle cx="135" cy="15" r="12" fill="#3b82f6" />
                <text x="135" y="20" textAnchor="middle" fontSize="12" fill="white">✓</text>
              </g>
            )}
          </g>

          {/* Conditional Diamond after Offer Agent */}
          <g transform="translate(550, 83)">
            <polygon
              points="17,0 34,17 17,34 0,17"
              fill="#fef3c7"
              stroke="#f59e0b"
              strokeWidth="2"
            />
            <text x="17" y="21" textAnchor="middle" fontSize="12" fill="#92400e">?</text>
          </g>

          {/* Arrow: Offer Agent → Diamond */}
          <line x1="530" y1="100" x2="550" y2="100" stroke={getPhaseStatus('offer_agent') === 'complete' ? '#3b82f6' : '#cbd5e1'} strokeWidth="2" />

          {/* Arrow: Diamond → Delivery (offer made) */}
          <line x1="584" y1="100" x2="620" y2="100" stroke={offerMade ? '#10b981' : '#cbd5e1'} strokeWidth="2" markerEnd="url(#arrow-green)" />
          <text x="602" y="92" textAnchor="middle" fontSize="8" fill="#16a34a">offer</text>

          {/* Exit path for no offer */}
          {offerExit && (
            <g>
              <path
                d="M 567 117 L 567 170 L 720 170"
                fill="none"
                stroke="#ef4444"
                strokeWidth="2"
                markerEnd="url(#arrow-red)"
              />
              <text x="640" y="185" textAnchor="middle" fontSize="9" fill="#dc2626">NO OFFER</text>
            </g>
          )}

          {/* Phase 3: Delivery */}
          <g
            transform="translate(620, 50)"
            onClick={() => handlePhaseClick('delivery')}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width="130"
              height="100"
              rx="12"
              fill={getPhaseStatus('delivery') === 'complete' ? '#ecfdf5' :
                    getPhaseStatus('delivery') === 'processing' ? '#dbeafe' : '#f8fafc'}
              stroke={getPhaseStatus('delivery') === 'complete' ? '#10b981' :
                      getPhaseStatus('delivery') === 'processing' ? '#3b82f6' : '#cbd5e1'}
              strokeWidth={getPhaseStatus('delivery') === 'processing' ? 3 : 2}
              className={getPhaseStatus('delivery') === 'processing' ? 'animate-pulse' : ''}
            />
            <text x="65" y="35" textAnchor="middle" fontSize="28">📬</text>
            <text x="65" y="58" textAnchor="middle" fontSize="12" fill="#374151" fontWeight="700">Delivery</text>
            <rect x="15" y="68" width="100" height="18" rx="4" fill="#64748b" />
            <text x="65" y="81" textAnchor="middle" fontSize="9" fill="white">WORKFLOW + LLM</text>
            {getPhaseStatus('delivery') === 'complete' && (
              <g>
                <circle cx="115" cy="15" r="12" fill="#10b981" />
                <text x="115" y="20" textAnchor="middle" fontSize="12" fill="white">✓</text>
              </g>
            )}
          </g>

          {/* Arrow: Delivery → END */}
          <line x1="750" y1="100" x2="770" y2="100" stroke={getPhaseStatus('delivery') === 'complete' ? '#10b981' : '#cbd5e1'} strokeWidth="2" />

          {/* END Node */}
          <g transform="translate(770, 85)">
            <circle r="15" cx="15" cy="15" fill="#dc2626" stroke="#b91c1c" strokeWidth="2" />
            <rect x="8" y="10" width="14" height="10" fill="white" rx="1" />
            <text x="15" y="45" textAnchor="middle" fontSize="10" fill="#6b7280">END</text>
          </g>
        </svg>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-600 border-t border-slate-200 pt-4">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-slate-100 border-2 border-slate-400 flex items-center justify-center text-[8px]">⚡</div>
            <span>Workflow (2)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded bg-blue-100 border-2 border-blue-500 flex items-center justify-center text-[8px]">🧠</div>
            <span>Agent ReWOO (1)</span>
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
            <div className="w-6 h-0.5 bg-red-400"></div>
            <span>Exit</span>
          </div>
        </div>
      </div>

      {/* Phase Details Panel */}
      {showStatePanel && (
        <div className="mt-4 grid grid-cols-3 gap-4">
          {phases.map((phase) => (
            <div
              key={phase.id}
              className={`bg-slate-50 rounded-lg p-4 border transition-all cursor-pointer ${
                selectedPhase === phase.id
                  ? phase.id === 'offer_agent'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-emerald-500 bg-emerald-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
              onClick={() => handlePhaseClick(phase.id)}
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">{phase.icon}</span>
                <div>
                  <div className="font-semibold text-sm text-slate-800">{phase.name}</div>
                  <div className={`text-[10px] px-1.5 py-0.5 rounded inline-block ${
                    phase.type === 'agent' ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-600'
                  }`}>
                    {phase.type === 'agent' ? '🧠 AGENT' : '⚡ WORKFLOW'}
                  </div>
                </div>
              </div>

              <div className="text-xs text-slate-500 mb-3">{phase.description}</div>

              <div className="space-y-2">
                {phase.subSteps.map((step) => {
                  const stepResult = agentResults[step.id];
                  const isRunning = currentAgentId === step.id;
                  return (
                    <div
                      key={step.id}
                      className={`flex items-center gap-2 p-2 rounded text-xs ${
                        stepResult?.status === 'complete'
                          ? 'bg-emerald-100 text-emerald-800'
                          : isRunning
                            ? 'bg-blue-100 text-blue-800 animate-pulse'
                            : 'bg-slate-100 text-slate-600'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAgent(step.id);
                      }}
                    >
                      <span>{step.icon}</span>
                      <span className="flex-1">{step.name}</span>
                      {stepResult?.status === 'complete' && <span>✓</span>}
                      {isRunning && <span className="animate-spin">⏳</span>}
                    </div>
                  );
                })}
              </div>

              {/* Show summary for completed phases */}
              {getPhaseStatus(phase.id) === 'complete' && (
                <div className="mt-3 pt-3 border-t border-slate-200">
                  <div className="text-[10px] text-slate-500 mb-1">Summary:</div>
                  {phase.subSteps.map((step) => {
                    const stepResult = agentResults[step.id];
                    return stepResult?.summary ? (
                      <div key={step.id} className="text-[10px] text-slate-600 truncate">
                        {stepResult.summary}
                      </div>
                    ) : null;
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Code Reference */}
      <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-3 font-mono text-xs">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-slate-500"># Pipeline Architecture</span>
            <span className="text-slate-700 ml-2">
              <span className="text-purple-600">Pre-checks</span>
              <span className="text-slate-400"> → </span>
              <span className="text-blue-600">Offer Agent (ReWOO)</span>
              <span className="text-slate-400"> → </span>
              <span className="text-emerald-600">Delivery</span>
            </span>
          </div>
          <div className="text-slate-400 text-[10px]">
            1 Agent + 2 Workflows
          </div>
        </div>
      </div>
    </div>
  );
}
