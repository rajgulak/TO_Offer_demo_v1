import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { ArchitectureOverview } from './components/ArchitectureOverview';
import { PNRSelector } from './components/PNRSelector';
import { ContextPanel } from './components/ContextPanel';
import { PipelineVisualization } from './components/PipelineVisualization';
import { AgentDetailPanel } from './components/AgentDetailPanel';
import { FinalDecisionPanel } from './components/FinalDecisionPanel';
import { InteractiveTutorial } from './components/InteractiveTutorial';
import { DemoControls, type ExecutionMode } from './components/DemoControls';
import { HITLPanel } from './components/HITLPanel';
import BusinessAgentDemo from './components/BusinessAgentDemo';
import { useSSE } from './hooks/useSSE';
import type { PNRSummary, EnrichedPNR, AgentResult, FinalDecision } from './types';

type DemoMode = 'technical' | 'business';

// TO Offer Prototype: 4 Workflows + 1 Agent + 1 LLM Call
// Only Offer Orchestration is a true "agent" (complex multi-factor decision with explainability)
const AGENT_CONFIG = [
  { id: 'customer_intelligence', name: 'Customer Intelligence', short_name: 'Customer', icon: 'brain', description: 'Checks eligibility (3 yes/no rules)', component_type: 'workflow' as const },
  { id: 'flight_optimization', name: 'Flight Optimization', short_name: 'Flight', icon: 'chart', description: 'Looks up cabin inventory data', component_type: 'workflow' as const },
  { id: 'offer_orchestration', name: 'Offer Orchestration', short_name: 'Offer', icon: 'scale', description: 'Complex 15+ factor decision - THE ONLY AGENT', component_type: 'agent' as const },
  { id: 'personalization', name: 'Personalization', short_name: 'Message', icon: 'sparkles', description: 'LLM generates personalized message', component_type: 'llm' as const },
  { id: 'channel_timing', name: 'Channel & Timing', short_name: 'Channel', icon: 'phone', description: 'Rule-based channel selection', component_type: 'workflow' as const },
  { id: 'measurement', name: 'Measurement & Learning', short_name: 'Measure', icon: 'trending', description: 'Random A/B assignment', component_type: 'workflow' as const },
];

// Use environment variable or default to localhost for dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  // Demo mode: 'business' for executive-friendly view, 'technical' for full details
  const [demoMode, setDemoMode] = useState<DemoMode>('business');

  const [pnrList, setPnrList] = useState<PNRSummary[]>([]);
  const [selectedPNR, setSelectedPNR] = useState<string | null>(null);
  const [enrichedData, setEnrichedData] = useState<EnrichedPNR | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<'idle' | 'running' | 'complete'>('idle');
  const [agentResults, setAgentResults] = useState<Record<string, AgentResult>>({});
  const [currentAgentId, setCurrentAgentId] = useState<string | null>(null);
  const [selectedAgentTab, setSelectedAgentTab] = useState<string | null>(null);
  const [finalDecision, setFinalDecision] = useState<FinalDecision | null>(null);
  const [isTutorialOpen, setIsTutorialOpen] = useState(false);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('choreography');
  const [hitlEnabled, setHitlEnabled] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_hitlPendingId, setHitlPendingId] = useState<string | null>(null);
  // Track execution mode actually being used (for live visualization)
  const [activeExecutionMode, setActiveExecutionMode] = useState<ExecutionMode | null>(null);
  const [plannerState, setPlannerState] = useState<{ isActive: boolean; plan?: string[]; reasoning?: string }>({ isActive: false });

  const { startEvaluation, startEvaluationHITL } = useSSE();

  // Fetch PNR list on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/pnrs`)
      .then(res => res.json())
      .then(data => setPnrList(data))
      .catch(err => console.error('Failed to fetch PNRs:', err));
  }, []);

  // Fetch enriched data when PNR selected
  useEffect(() => {
    if (!selectedPNR) {
      setEnrichedData(null);
      return;
    }

    fetch(`${API_BASE}/api/pnrs/${selectedPNR}`)
      .then(res => res.json())
      .then(data => setEnrichedData(data))
      .catch(err => console.error('Failed to fetch PNR data:', err));
  }, [selectedPNR]);

  const handleSelectPNR = useCallback((pnr: string) => {
    setSelectedPNR(pnr);
    // Reset state
    setPipelineStatus('idle');
    setAgentResults({});
    setCurrentAgentId(null);
    setSelectedAgentTab(null);
    setFinalDecision(null);
    setActiveExecutionMode(null);
    setPlannerState({ isActive: false });
  }, []);

  const handleRunEvaluation = useCallback(async () => {
    if (!selectedPNR) return;

    // Reset state
    setPipelineStatus('running');
    setAgentResults({});
    setCurrentAgentId(null);
    setSelectedAgentTab(null);
    setFinalDecision(null);
    setHitlPendingId(null);
    setActiveExecutionMode(executionMode);
    setPlannerState({ isActive: false });

    // If HITL is enabled, use the HITL endpoint
    if (hitlEnabled) {
      try {
        const result = await startEvaluationHITL(selectedPNR, true);

        if (result.status === 'pending_approval') {
          // Offer is waiting for human approval
          setHitlPendingId(result.approval_request_id || null);
          setPipelineStatus('complete');
          setFinalDecision({
            should_send_offer: true,
            offer_type: result.proposed_offer?.offer_type || 'Unknown',
            price: result.proposed_offer?.price || 0,
            pending_approval: true,
            approval_request_id: result.approval_request_id,
            escalation_reasons: result.escalation_reasons,
          });
        } else if (result.final_decision) {
          // No approval needed, offer sent directly
          setPipelineStatus('complete');
          setFinalDecision(result.final_decision);
        } else {
          // No offer
          setPipelineStatus('complete');
          setFinalDecision({
            should_send_offer: false,
            suppression_reason: result.suppression_reason || 'No offer criteria met',
          });
        }
      } catch (error) {
        console.error('HITL evaluation error:', error);
        setPipelineStatus('idle');
      }
      return;
    }

    // Standard SSE evaluation
    startEvaluation(selectedPNR, {
      onPipelineStart: () => {
        setPipelineStatus('running');
      },
      onPlannerStart: () => {
        setPlannerState({ isActive: true });
      },
      onPlannerDecision: (data) => {
        setPlannerState({ isActive: false, plan: data.plan, reasoning: data.reasoning });
      },
      onAgentStart: (data) => {
        setCurrentAgentId(data.agent_id);
      },
      onAgentComplete: (data) => {
        setAgentResults(prev => ({
          ...prev,
          [data.agent_id]: {
            agent_id: data.agent_id,
            agent_name: data.agent_name,
            step: data.step,
            status: 'complete',
            duration_ms: data.duration_ms,
            summary: data.summary,
            reasoning: data.reasoning,
            outputs: data.outputs,
          }
        }));
        setCurrentAgentId(null);
        // Auto-select the completed agent tab
        setSelectedAgentTab(data.agent_id);
      },
      onAgentSkip: (data) => {
        setAgentResults(prev => ({
          ...prev,
          [data.agent_id]: {
            agent_id: data.agent_id,
            agent_name: data.agent_name,
            step: data.step,
            status: 'skipped',
            duration_ms: 0,
            summary: data.reason,
            reasoning: `Skipped: ${data.reason}`,
            outputs: {},
          }
        }));
      },
      onPipelineComplete: (data) => {
        setPipelineStatus('complete');
        setCurrentAgentId(null);
        setFinalDecision(data.final_decision);
        // Keep activeExecutionMode to show completed state in visualization
      },
      onError: (error) => {
        console.error('Pipeline error:', error);
        setPipelineStatus('idle');
        setCurrentAgentId(null);
        setActiveExecutionMode(null);
      }
    }, executionMode);
  }, [selectedPNR, startEvaluation, startEvaluationHITL, hitlEnabled, executionMode]);

  // If business mode, render the focused business demo
  if (demoMode === 'business') {
    return (
      <div className="relative">
        {/* Mode Switcher - Fixed Top Right */}
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-slate-800/90 backdrop-blur rounded-xl p-1 shadow-lg border border-slate-700">
          <button
            onClick={() => setDemoMode('business')}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all bg-cyan-600 text-white"
          >
            Business View
          </button>
          <button
            onClick={() => setDemoMode('technical')}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all text-slate-400 hover:text-white"
          >
            Technical View
          </button>
        </div>

        <BusinessAgentDemo />
      </div>
    );
  }

  // Technical mode - original full demo
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Mode Switcher - Fixed Top Right */}
      <div className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-white/90 backdrop-blur rounded-xl p-1 shadow-lg border border-slate-200">
        <button
          onClick={() => setDemoMode('business')}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-all text-slate-600 hover:text-slate-900"
        >
          Business View
        </button>
        <button
          onClick={() => setDemoMode('technical')}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-all bg-blue-600 text-white"
        >
          Technical View
        </button>
      </div>

      <Header />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Architecture Overview - Collapsible */}
        <ArchitectureOverview onOpenTutorial={() => setIsTutorialOpen(true)} />

        {/* Demo Controls - Execution Mode & HITL Toggle */}
        <DemoControls
          executionMode={executionMode}
          onExecutionModeChange={setExecutionMode}
          hitlEnabled={hitlEnabled}
          onHitlEnabledChange={setHitlEnabled}
        />

        {/* HITL Approval Queue */}
        <HITLPanel
          isEnabled={hitlEnabled}
          onApprovalComplete={() => {
            // Refresh the UI when an approval is processed
            setHitlPendingId(null);
          }}
        />

        {/* PNR Selector */}
        <PNRSelector
          pnrList={pnrList}
          selectedPNR={selectedPNR}
          onSelect={handleSelectPNR}
          onRun={handleRunEvaluation}
          isRunning={pipelineStatus === 'running'}
        />

        {/* Context Panel (Customer/Flight) */}
        <ContextPanel data={enrichedData} />

        {/* Pipeline Visualization */}
        <PipelineVisualization
          agents={AGENT_CONFIG}
          agentResults={agentResults}
          currentAgentId={currentAgentId}
          selectedAgentTab={selectedAgentTab}
          onSelectAgent={setSelectedAgentTab}
          executionMode={activeExecutionMode}
          hitlEnabled={hitlEnabled}
          plannerState={plannerState}
        />

        {/* Agent Detail Panel */}
        <AgentDetailPanel
          agents={AGENT_CONFIG}
          agentResults={agentResults}
          selectedAgentTab={selectedAgentTab}
          onSelectTab={setSelectedAgentTab}
        />

        {/* Final Decision */}
        <FinalDecisionPanel
          decision={finalDecision}
          isComplete={pipelineStatus === 'complete'}
        />
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-sm text-gray-500">
        TO Offer Prototype - 4 Workflows + 1 Agent + 1 LLM Call
      </footer>

      {/* Interactive Tutorial Modal */}
      <InteractiveTutorial
        isOpen={isTutorialOpen}
        onClose={() => setIsTutorialOpen(false)}
      />
    </div>
  );
}

export default App;
