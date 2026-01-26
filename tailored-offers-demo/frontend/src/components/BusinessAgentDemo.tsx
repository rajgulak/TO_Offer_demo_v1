/**
 * Business Agent Demo - Visual Showcase of Offer Agent Decision Making
 *
 * This component connects to the real LangGraph backend via SSE streaming
 * to show how the Offer Agent makes decisions.
 *
 * How it works (in plain English):
 * - Backend: Real LangGraph agents evaluate the customer
 * - Planner: Agent looks at customer data and plans what to check
 * - Worker: Agent executes each check via MCP tools
 * - Solver: Agent synthesizes results and makes final decision
 * - Personalization: LLM generates personalized message
 *
 * Key Features:
 * - Real API integration with SSE streaming
 * - Live reasoning display from actual backend
 * - Shows ReWOO pattern (Planner-Worker-Solver) execution
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useSSE } from '../hooks/useSSE';
import { mapToFinalDecision } from '../utils/parseOfferReasoning';
import { PromptEditor } from './PromptEditor';
import { ExplainerVideo } from './ExplainerVideo';
import { PromptAssistant } from './PromptAssistant';
import { PolicyConfig } from './PolicyConfig';
import { GuidedDemo } from './GuidedDemo';
import type {
  PNRSummary,
  EnrichedPNRResponse,
  AgentCompleteData,
  PipelineCompleteData,
} from '../types/backend';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types for UI display
interface AgentPhase {
  phase: 'idle' | 'loading' | 'planner' | 'worker' | 'solver' | 'complete';
  step?: number;
}

interface EvaluationResult {
  type: string;
  status: 'pending' | 'running' | 'complete';
  result?: string;
  recommendation?: string;
  stepId?: string;
}

// ReWOO plan step from backend
interface ReWOOPlanStep {
  step_id: string;
  evaluation_type: string;
  description: string;
}

interface FinalDecision {
  offerType: string;
  offerName: string;
  price: number;
  discount: number;
  expectedValue: number;
  confidence: string;
  channel: string;
  reasoning: string;
}

// Tier display names and colors
const TIER_NAMES: Record<string, string> = {
  'E': 'Executive Platinum',
  'T': 'Platinum Pro',
  'P': 'Platinum',
  'G': 'Gold',
  'R': 'Ruby',
  'N': 'General',
};

const TIER_COLORS: Record<string, string> = {
  'E': 'text-slate-300',
  'T': 'text-purple-400',
  'P': 'text-purple-400',
  'G': 'text-yellow-400',
  'R': 'text-red-400',
  'N': 'text-slate-400',
};

const TIER_BG: Record<string, string> = {
  'E': 'bg-slate-700/50 border-slate-400/50',
  'T': 'bg-purple-900/30 border-purple-500/50',
  'P': 'bg-purple-900/30 border-purple-500/50',
  'G': 'bg-yellow-900/30 border-yellow-500/50',
  'R': 'bg-red-900/30 border-red-500/50',
  'N': 'bg-slate-800/50 border-slate-600/50',
};

export default function BusinessAgentDemo() {
  // API state
  const [pnrList, setPnrList] = useState<PNRSummary[]>([]);
  const [enrichedData, setEnrichedData] = useState<EnrichedPNRResponse | null>(null);
  const [isLoadingPnr, setIsLoadingPnr] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // UI state
  const [selectedPNR, setSelectedPNR] = useState<string>('');
  const [agentPhase, setAgentPhase] = useState<AgentPhase>({ phase: 'idle' });
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [plannerThought, setPlannerThought] = useState<string>('');
  const [solverThought, setSolverThought] = useState<string>('');
  const [finalDecision, setFinalDecision] = useState<FinalDecision | null>(null);
  const [showingDecision, setShowingDecision] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<number>(0);
  const [hitlEnabled, setHitlEnabled] = useState(false);
  const [hitlPending, setHitlPending] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<FinalDecision | null>(null);

  // Ref to track latest hitlEnabled value (avoids stale closure issues)
  const hitlEnabledRef = useRef(hitlEnabled);
  useEffect(() => {
    hitlEnabledRef.current = hitlEnabled;
  }, [hitlEnabled]);

  // Pre-flight agent results
  const [preFlightAgents, setPreFlightAgents] = useState<AgentCompleteData[]>([]);

  // ReWOO plan state (used by ReWOO streaming events)
  const [, setRewooPlan] = useState<ReWOOPlanStep[]>([]);
  const [, setRewooOfferOptions] = useState<unknown[]>([]);

  // Control panel state
  const [showControlPanel, setShowControlPanel] = useState(false);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [advancedTab, setAdvancedTab] = useState<'policies' | 'prompts'>('policies');
  const [promptEditorAgent, setPromptEditorAgent] = useState<string>('offer_orchestration.planner');

  // Guided demo state
  const [promptAssistantOpen, setPromptAssistantOpen] = useState(false);

  // Dynamic data for GuidedDemo contextual narration
  const [guidedDemoPlannerInfo, setGuidedDemoPlannerInfo] = useState<{
    reasoning: string;
    plan: Array<{ step_id: string; evaluation_type: string; description: string }>;
    offer_options: Array<{ offer_type: string; cabin: string }>;
  } | null>(null);

  const [guidedDemoWorkerInfo, setGuidedDemoWorkerInfo] = useState<{
    evaluations: Array<{ type: string; recommendation: string; reasoning?: string }>;
  } | null>(null);

  const [guidedDemoSolverInfo, setGuidedDemoSolverInfo] = useState<{
    selected_offer: string;
    offer_price: number;
    discount_applied: number;
    expected_value: number;
    reasoning: string;
    confidence?: number;
  } | null>(null);

  // Progressive data reveal - sync with pipeline steps
  // Step 1: Flights, Step 2: PNRs, Step 3: Passengers (Customer), Step 4: ML Score, Step 5: Policy, Step 6: Decision
  const showFlightData = pipelineStep >= 1;
  const showCustomerData = pipelineStep >= 3;
  const showMLScore = pipelineStep >= 4;
  const showEligibility = pipelineStep >= 5;

  // SSE hook
  const { startEvaluation, startEvaluationHITL } = useSSE();

  // Fetch PNR list on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/pnrs`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch PNRs');
        return res.json();
      })
      .then((data: PNRSummary[]) => {
        setPnrList(data);
        if (data.length > 0 && !selectedPNR) {
          setSelectedPNR(data[0].pnr);
        }
      })
      .catch(err => {
        setApiError(`Failed to load PNRs: ${err.message}`);
      });
  }, []);

  // Fetch enriched data when PNR selected
  useEffect(() => {
    if (!selectedPNR) return;

    setIsLoadingPnr(true);
    setApiError(null);

    fetch(`${API_BASE}/api/pnrs/${selectedPNR}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch PNR details');
        return res.json();
      })
      .then((data: EnrichedPNRResponse) => {
        setEnrichedData(data);
        setIsLoadingPnr(false);
      })
      .catch(err => {
        setApiError(`Failed to load PNR: ${err.message}`);
        setIsLoadingPnr(false);
      });
  }, [selectedPNR]);

  // Reset UI when PNR changes
  useEffect(() => {
    setAgentPhase({ phase: 'idle' });
    setEvaluations([]);
    setPlannerThought('');
    setSolverThought('');
    setFinalDecision(null);
    setShowingDecision(false);
    setPipelineStep(0);
    setHitlPending(false);
    // Reset guided demo data
    setGuidedDemoPlannerInfo(null);
    setGuidedDemoWorkerInfo(null);
    setGuidedDemoSolverInfo(null);
    setPendingDecision(null);
    setPreFlightAgents([]);
    setRewooPlan([]);
    setRewooOfferOptions([]);
  }, [selectedPNR]);

  // Run the agent evaluation via SSE
  const runAgent = useCallback(async () => {
    if (!selectedPNR) return;

    // Reset state
    setAgentPhase({ phase: 'loading' });
    setEvaluations([]);
    setPlannerThought('');
    setSolverThought('');
    setFinalDecision(null);
    setShowingDecision(false);
    setPipelineStep(0);
    setHitlPending(false);
    // Reset guided demo data
    setGuidedDemoPlannerInfo(null);
    setGuidedDemoWorkerInfo(null);
    setGuidedDemoSolverInfo(null);
    setPendingDecision(null);
    setPreFlightAgents([]);
    setRewooPlan([]);
    setRewooOfferOptions([]);

    // Always use SSE streaming to show reasoning steps
    // If HITL enabled, we'll check for approval at the end
    startEvaluation(selectedPNR, {
      onPipelineStart: () => {
        setPipelineStep(1);
        // Animate through pipeline steps
        setTimeout(() => setPipelineStep(2), 200);
        setTimeout(() => setPipelineStep(3), 400);
      },

      onPlannerStart: () => {
        // Legacy pipeline-level planner (not ReWOO) - no-op
      },

      onPlannerDecision: () => {
        // Legacy pipeline-level planner (not ReWOO) - no-op
      },

      onAgentStart: (data) => {
        const step = data.step;

        // Update pipeline visualization
        if (step <= 2) {
          setPipelineStep(3 + step);
        }

        // Pre-flight agents (customer_intelligence, flight_optimization)
        if (['customer_intelligence', 'flight_optimization'].includes(data.agent_id)) {
          // Still in loading phase for pre-flight agents
          setAgentPhase({ phase: 'loading' });
        }

        // Offer orchestration starts the Planner phase (ReWOO will stream details)
        if (data.agent_id === 'offer_orchestration') {
          setAgentPhase({ phase: 'planner' });
          setPlannerThought('🎯 ReWOO Planner analyzing customer and offers...');
        }

        // Personalization is part of Solver phase
        if (data.agent_id === 'personalization') {
          // Stay in solver phase, personalization adds to it
        }
      },

      // NEW: Handle ReWOO Planner completion
      onReWOOPlannerComplete: (data) => {
        setRewooPlan(data.plan);
        setRewooOfferOptions(data.offer_options);

        // Build planner thought from plan
        const planSteps = data.plan.map((s: ReWOOPlanStep) =>
          `  ${s.step_id}: [${s.evaluation_type}] ${s.description}`
        ).join('\n');

        setPlannerThought(
          `📋 ReWOO Planner Complete\n\n` +
          `Reasoning: ${data.reasoning}\n\n` +
          `Plan has ${data.plan.length} evaluation steps:\n${planSteps}`
        );

        // Initialize evaluations as pending
        const pendingEvals: EvaluationResult[] = data.plan.map((s: ReWOOPlanStep) => ({
          type: s.evaluation_type,
          status: 'pending' as const,
          stepId: s.step_id,
          result: s.description,
        }));
        setEvaluations(pendingEvals);

        // Set guided demo planner info for dynamic narration
        setGuidedDemoPlannerInfo({
          reasoning: data.reasoning,
          plan: data.plan.map((s: ReWOOPlanStep) => ({
            step_id: s.step_id,
            evaluation_type: s.evaluation_type,
            description: s.description,
          })),
          offer_options: (data.offer_options || []).map((o: any) => ({
            offer_type: o.offer_type || o.type || 'Unknown',
            cabin: o.cabin || o.name || 'Unknown',
          })),
        });

        // Initialize guided demo worker info
        setGuidedDemoWorkerInfo({ evaluations: [] });

        // Transition to Worker phase
        setAgentPhase({ phase: 'worker' });
      },

      // NEW: Handle ReWOO Worker step completion
      onReWOOWorkerStep: (data) => {
        // Update the specific evaluation step
        setEvaluations(prev => prev.map(e =>
          e.stepId === data.step_id
            ? {
                ...e,
                status: 'complete' as const,
                recommendation: data.reasoning,
              }
            : e
        ));

        // Update guided demo worker info for dynamic narration
        setGuidedDemoWorkerInfo(prev => ({
          evaluations: [
            ...(prev?.evaluations || []),
            {
              type: data.evaluation_type,
              recommendation: data.recommendation || data.reasoning || '',
              reasoning: data.reasoning,
            },
          ],
        }));
      },

      // NEW: Handle ReWOO Solver completion
      onReWOOSolverComplete: (data) => {
        setAgentPhase({ phase: 'solver' });

        const decision = data.decision;
        const offerNames: Record<string, string> = {
          'IU_BUSINESS': 'Business Class',
          'IU_PREMIUM_ECONOMY': 'Premium Economy',
          'MCE': 'Main Cabin Extra',
        };

        const offerName = offerNames[decision.selected_offer] || decision.selected_offer;
        const discountText = decision.discount_applied > 0
          ? `\n   Discount: ${(decision.discount_applied * 100).toFixed(0)}%`
          : '';
        const policiesText = decision.policies_applied?.length > 0
          ? `\n   Policies: ${decision.policies_applied.join(', ')}`
          : '';

        setSolverThought(
          `✅ ReWOO Solver Complete\n\n` +
          `SYNTHESIS: ${decision.reasoning}\n\n` +
          `FINAL DECISION: ${offerName} @ $${decision.offer_price?.toFixed(0)}` +
          discountText +
          policiesText +
          `\n   Expected Value: $${decision.expected_value?.toFixed(2)}`
        );

        // Set guided demo solver info for dynamic narration
        setGuidedDemoSolverInfo({
          selected_offer: offerName,
          offer_price: decision.offer_price || 0,
          discount_applied: decision.discount_applied ? decision.discount_applied * 100 : 0,
          expected_value: decision.expected_value || 0,
          reasoning: decision.reasoning || '',
        });
      },

      onAgentComplete: (data) => {
        handleAgentComplete(data);
      },

      onAgentSkip: (data) => {
        // Agent skipped (e.g., customer not eligible)
        if (data.agent_id === 'offer_orchestration') {
          setSolverThought(`❌ Evaluation skipped\n\nReason: ${data.reason}`);
        }
      },

      onPipelineComplete: (data) => {
        handlePipelineComplete(data);
      },

      onError: (error) => {
        setApiError(error);
        setAgentPhase({ phase: 'idle' });
      },
    }, 'planner-worker');
  }, [selectedPNR, hitlEnabled, startEvaluation, startEvaluationHITL]);

  // Handle agent completion
  const handleAgentComplete = useCallback((data: AgentCompleteData) => {
    // Pre-flight agents
    if (['customer_intelligence', 'flight_optimization'].includes(data.agent_id)) {
      setPreFlightAgents(prev => [...prev, data]);

      // Check for early termination (customer not eligible)
      if (data.agent_id === 'customer_intelligence' && data.outputs?.customer_eligible === false) {
        setSolverThought(`❌ Customer Not Eligible\n\nReason: ${data.outputs?.suppression_reason || 'Customer criteria not met'}\n\nNo offer will be sent.`);
        setAgentPhase({ phase: 'complete' });
        setFinalDecision({
          offerType: 'SUPPRESSED',
          offerName: `No Offer (${data.outputs?.suppression_reason || 'Not Eligible'})`,
          price: 0,
          discount: 0,
          expectedValue: 0,
          confidence: 'N/A',
          channel: 'N/A',
          reasoning: data.outputs?.suppression_reason as string || 'Customer did not meet eligibility criteria',
        });
        setShowingDecision(true);
      }
      return;
    }

    // Offer orchestration - ReWOO phases are now handled by separate events
    // (onReWOOPlannerComplete, onReWOOWorkerStep, onReWOOSolverComplete)
    // This callback just handles the final agent_complete signal
    if (data.agent_id === 'offer_orchestration') {
      // ReWOO streaming already handled the details, no need to parse reasoning
      return;
    }

    // Personalization agent adds to solver thought
    if (data.agent_id === 'personalization') {
      setSolverThought(prev => {
        return `${prev}\n\n💬 Personalized Message Generated:\n"${data.outputs?.message_body || data.summary}"`;
      });
    }
  }, []);

  // Handle pipeline completion
  const handlePipelineComplete = useCallback(async (data: PipelineCompleteData) => {
    setPipelineStep(6);

    const mapped = mapToFinalDecision(data.final_decision);

    // Use ref to get latest hitlEnabled value (avoids stale closure from guided demo)
    const isHitlEnabled = hitlEnabledRef.current;

    // If HITL enabled, set pending state IMMEDIATELY (before async call)
    // This prevents the guided demo from proceeding before we check HITL status
    if (isHitlEnabled && selectedPNR && data.final_decision?.should_send_offer !== false) {
      // Set pending state first to block guided demo
      setHitlPending(true);
      setPendingDecision(mapped);
      setAgentPhase({ phase: 'complete' });

      try {
        const hitlResult = await startEvaluationHITL(selectedPNR, true);

        if (hitlResult.status === 'pending_approval') {
          // Show pending approval state
          setSolverThought(prev =>
            `${prev}\n\n⏸️ HUMAN-IN-THE-LOOP ENABLED\n\nAgent recommendation is ready.\nAwaiting human approval before sending offer...\n\nReason: ${hitlResult.approval_reason_details || 'Manual review requested'}`
          );
          return;
        }
      } catch (err) {
        // If HITL check fails, proceed with normal flow
        console.error('HITL check failed:', err);
      }

      // HITL not actually pending, clear the state
      setHitlPending(false);
      setPendingDecision(null);
    }

    setAgentPhase({ phase: 'complete' });
    setFinalDecision(mapped);
    setShowingDecision(true);
  }, [selectedPNR, startEvaluationHITL]);

  // HITL Approval handler
  const handleApprove = useCallback(() => {
    if (pendingDecision) {
      setFinalDecision(pendingDecision);
      setHitlPending(false);
      setPendingDecision(null);
      setSolverThought(prev => prev + `\n\n✅ APPROVED by human reviewer`);
      setShowingDecision(true);
    }
  }, [pendingDecision]);

  // HITL Reject handler
  const handleReject = useCallback(() => {
    setFinalDecision({
      offerType: 'REJECTED',
      offerName: 'Offer Rejected by Reviewer',
      price: 0,
      discount: 0,
      expectedValue: 0,
      confidence: 'N/A',
      channel: 'N/A',
      reasoning: 'Human reviewer rejected this offer',
    });
    setHitlPending(false);
    setPendingDecision(null);
    setSolverThought(prev => prev + `\n\n❌ REJECTED by human reviewer`);
    setShowingDecision(true);
  }, []);

  // Derive display data from enrichedData
  const customer = enrichedData?.customer;
  const flight = enrichedData?.flight;
  const reservation = enrichedData?.reservation;

  // Calculate estimated LDF from cabin data
  const calculateAverageLDF = () => {
    if (!flight?.cabins) return 75;
    const cabins = Object.values(flight.cabins);
    if (cabins.length === 0) return 75;
    const sum = cabins.reduce((acc, c) => acc + (c.expected_load_factor || 75), 0);
    return Math.round(sum / cabins.length);
  };

  const estimatedLDF = calculateAverageLDF();
  const mlScore = 0.72; // Placeholder - ML scores shown separately

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <span className="text-3xl">🎯</span>
              Offer Agent Demo
            </h1>
            <p className="text-slate-400 mt-1">
              Watch how the agent decides which upgrade offer to give each customer
            </p>
            <p className="text-slate-500 text-sm mt-1">
              Connected to real LangGraph backend • ReWOO Pattern (Planner → Worker → Solver)
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* HITL Toggle */}
            <div data-tour="hitl-toggle" className="flex items-center gap-2 bg-slate-700 rounded-lg px-3 py-2">
              <div className="flex flex-col items-start">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-300">Human + AI</span>
                  <span className="text-[8px] bg-emerald-600 text-white px-1.5 py-0.5 rounded-full font-bold">
                    P5
                  </span>
                </div>
              </div>
              <button
                onClick={() => setHitlEnabled(!hitlEnabled)}
                className={`relative w-12 h-6 rounded-full transition-all ${
                  hitlEnabled ? 'bg-amber-500' : 'bg-slate-600'
                }`}
              >
                <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${
                  hitlEnabled ? 'left-7' : 'left-1'
                }`} />
              </button>
              <span className={`text-xs ${hitlEnabled ? 'text-amber-400' : 'text-slate-500'}`}>
                {hitlEnabled ? 'ON' : 'OFF'}
              </span>
            </div>

            {/* PNR Selector */}
            <div data-tour="customer-selector" className="flex items-center gap-3">
              <select
                value={selectedPNR}
                onChange={(e) => setSelectedPNR(e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white"
                disabled={pnrList.length === 0}
              >
                {pnrList.length === 0 ? (
                  <option>Loading PNRs...</option>
                ) : (
                  pnrList.map(pnr => (
                    <option key={pnr.pnr} value={pnr.pnr}>
                      {pnr.pnr} - {pnr.customer_name} ({pnr.scenario_tag})
                    </option>
                  ))
                )}
              </select>

              <button
                onClick={runAgent}
                disabled={(agentPhase.phase !== 'idle' && agentPhase.phase !== 'complete') || hitlPending || !selectedPNR || isLoadingPnr}
                className={`px-6 py-2 rounded-lg font-medium transition-all ${
                  (agentPhase.phase === 'idle' || agentPhase.phase === 'complete') && !hitlPending && selectedPNR && !isLoadingPnr
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                    : 'bg-slate-600 text-slate-400 cursor-not-allowed'
                }`}
              >
                {isLoadingPnr ? '⏳ Loading...' :
                 agentPhase.phase === 'idle' ? '▶ Run Agent' :
                 agentPhase.phase === 'complete' && !hitlPending ? '↻ Run Again' : '⏳ Running...'}
              </button>
            </div>
          </div>
        </div>

        {/* API Error Display */}
        {apiError && (
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2 text-red-400">
              <span>⚠️</span>
              <span>{apiError}</span>
              <button
                onClick={() => setApiError(null)}
                className="ml-auto text-red-300 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* ========== CONTROL PANEL ========== */}
        <div data-tour="control-panel" className="bg-gradient-to-r from-cyan-900/30 via-slate-800/50 to-purple-900/30 rounded-2xl border border-cyan-500/30 mb-6 overflow-hidden">
          {/* Header - Always Visible */}
          <div
            className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-700/20 transition-colors"
            onClick={() => setShowControlPanel(!showControlPanel)}
          >
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎛️</span>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold">Control Agent Behavior</h2>
                    <span className="text-[10px] bg-amber-600 text-white px-2 py-0.5 rounded-full font-bold">
                      PILLAR 3: BUSINESS CONTROL
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    {advancedMode
                      ? 'Change policies & prompts instantly - no IT ticket'
                      : 'Plain English instructions - no code required'
                    }
                  </p>
                </div>
              </div>

              {/* Quick Phase Indicators - Only in Advanced Mode */}
              {advancedMode && (
                <div className="flex items-center gap-1 ml-4">
                  {[
                    { id: 'offer_orchestration.planner', icon: '📋', label: 'Planner' },
                    { id: 'offer_orchestration.worker', icon: '⚙️', label: 'Worker' },
                    { id: 'offer_orchestration.solver', icon: '✅', label: 'Solver' },
                    { id: 'personalization', icon: '💬', label: 'Message' },
                  ].map((phase) => (
                    <div
                      key={phase.id}
                      className={`px-2 py-1 rounded text-xs flex items-center gap-1 ${
                        promptEditorAgent === phase.id
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-700/50 text-slate-400'
                      }`}
                    >
                      <span>{phase.icon}</span>
                      <span className="hidden sm:inline">{phase.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              {/* Advanced Mode Toggle */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setAdvancedMode(!advancedMode);
                  if (!advancedMode) setShowControlPanel(true);
                }}
                className={`text-xs px-3 py-1 rounded-full transition-all ${
                  advancedMode
                    ? 'bg-amber-600 text-white'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {advancedMode ? '🔧 Advanced Mode' : '🔧 Advanced'}
              </button>
              <span className="text-xs text-purple-400 bg-purple-900/50 px-3 py-1 rounded-full">
                🤖 Use Prompt Assistant
              </span>
              <svg
                className={`w-6 h-6 text-slate-400 transition-transform ${showControlPanel ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Expanded Content */}
          {showControlPanel && (
            <div className="px-4 pb-4 space-y-4 border-t border-slate-700/50">
              {/* Business User View - Use Prompt Assistant */}
              {!advancedMode && (
                <div className="pt-4">
                  <div className="bg-gradient-to-r from-purple-900/30 to-indigo-900/30 border border-purple-500/30 rounded-xl p-6 text-center">
                    <div className="text-4xl mb-4">🤖</div>
                    <h3 className="text-xl font-bold text-white mb-2">Use the Prompt Assistant</h3>
                    <p className="text-slate-300 mb-4 max-w-md mx-auto">
                      Click the <span className="text-purple-400 font-semibold">purple robot button</span> in the bottom-left corner
                      to modify agent behavior using plain English instructions.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 mb-4">
                      <span className="bg-purple-800/50 text-purple-200 px-3 py-1 rounded-full text-sm">"Be more friendly"</span>
                      <span className="bg-purple-800/50 text-purple-200 px-3 py-1 rounded-full text-sm">"Focus on business travelers"</span>
                      <span className="bg-purple-800/50 text-purple-200 px-3 py-1 rounded-full text-sm">"Bigger discounts for VIPs"</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      The assistant validates all changes to keep the agent working correctly.
                    </p>
                  </div>
                </div>
              )}

              {/* Advanced Mode - Prompts & Policies */}
              {advancedMode && (
                <>
                  {/* Tab Selector: Policies vs Prompts */}
                  <div className="pt-4 flex gap-2">
                    <button
                      onClick={() => setAdvancedTab('policies')}
                      className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                        advancedTab === 'policies'
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      <span>📊</span> Policy Configuration
                    </button>
                    <button
                      onClick={() => setAdvancedTab('prompts')}
                      className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                        advancedTab === 'prompts'
                          ? 'bg-amber-600 text-white'
                          : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      <span>📝</span> Prompt Editor
                    </button>
                  </div>

                  {/* Policy Configuration Tab */}
                  {advancedTab === 'policies' && (
                    <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-700">
                      <PolicyConfig />
                    </div>
                  )}

                  {/* Prompts Tab */}
                  {advancedTab === 'prompts' && (
                    <>
                      {/* Warning Banner */}
                      <div className="bg-amber-900/30 border border-amber-500/30 rounded-lg px-4 py-3 flex items-start gap-3">
                        <span className="text-xl">⚠️</span>
                        <div>
                          <p className="text-amber-200 font-medium text-sm">Advanced Mode - For Prompt Engineers</p>
                          <p className="text-amber-300/70 text-xs mt-1">
                            Direct editing can break agent behavior. Use with caution.
                          </p>
                        </div>
                      </div>

                      {/* Phase Selector Tabs */}
                      <div className="flex gap-2">
                        {[
                          { id: 'offer_orchestration.planner', icon: '📋', label: 'Planner', color: 'cyan', desc: 'What to evaluate' },
                          { id: 'offer_orchestration.worker', icon: '⚙️', label: 'Worker', color: 'purple', desc: 'How to evaluate' },
                          { id: 'offer_orchestration.solver', icon: '✅', label: 'Solver', color: 'emerald', desc: 'How to decide' },
                          { id: 'personalization', icon: '💬', label: 'Message', color: 'amber', desc: 'How to write' },
                        ].map((phase) => (
                          <button
                            key={phase.id}
                            onClick={() => setPromptEditorAgent(phase.id)}
                            className={`flex-1 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                              promptEditorAgent === phase.id
                                ? phase.color === 'cyan' ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/30' :
                                  phase.color === 'purple' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30' :
                                  phase.color === 'emerald' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/30' :
                                  'bg-amber-600 text-white shadow-lg shadow-amber-500/30'
                                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                            }`}
                          >
                            <div className="text-xl mb-1">{phase.icon}</div>
                            <div className="font-semibold">{phase.label}</div>
                            <div className={`text-xs ${promptEditorAgent === phase.id ? 'text-white/70' : 'text-slate-500'}`}>
                              {phase.desc}
                            </div>
                          </button>
                        ))}
                      </div>

                      {/* Two Column Layout: Editor + Examples */}
                      <div className="grid grid-cols-3 gap-4">
                        {/* Prompt Editor - Takes 2 columns */}
                        <div className="col-span-2">
                          <PromptEditor
                            agentId={promptEditorAgent}
                            agentName={
                              promptEditorAgent === 'offer_orchestration.planner' ? 'Planner' :
                              promptEditorAgent === 'offer_orchestration.worker' ? 'Worker' :
                              promptEditorAgent === 'offer_orchestration.solver' ? 'Solver' :
                              'Message Generator'
                            }
                            onPromptUpdated={() => {}}
                          />
                        </div>

                        {/* Example Changes - 1 column */}
                        <div className="space-y-3">
                          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                            <div className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                              <span>💡</span> Example Changes
                            </div>
                            <ul className="text-xs text-slate-400 space-y-2">
                              {promptEditorAgent === 'offer_orchestration.planner' && (
                                <>
                                  <li className="p-2 bg-slate-900/50 rounded">"Always check inventory priority first"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Skip price sensitivity for Executive Platinum"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Add step to check recent purchase history"</li>
                                </>
                              )}
                              {promptEditorAgent === 'offer_orchestration.worker' && (
                                <>
                                  <li className="p-2 bg-slate-900/50 rounded">"Be more lenient with confidence thresholds"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Increase goodwill discount to 15%"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Prioritize high-inventory cabins aggressively"</li>
                                </>
                              )}
                              {promptEditorAgent === 'offer_orchestration.solver' && (
                                <>
                                  <li className="p-2 bg-slate-900/50 rounded">"Prioritize customer satisfaction over revenue"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Be aggressive with VIP discounts"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Consider inventory urgency heavily"</li>
                                </>
                              )}
                              {promptEditorAgent === 'personalization' && (
                                <>
                                  <li className="p-2 bg-slate-900/50 rounded">"Use a more casual, friendly tone"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Emphasize the upgrade benefits"</li>
                                  <li className="p-2 bg-slate-900/50 rounded">"Keep messages shorter and direct"</li>
                                </>
                              )}
                            </ul>
                          </div>

                          <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-200">
                            <strong>⚠️ Careful:</strong>
                            <ul className="mt-2 space-y-1 text-amber-300">
                              <li>• Test after every change</li>
                              <li>• Keep backup of working prompts</li>
                              <li>• Small changes are safer</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Decision Pipeline Flow */}
        <DecisionPipeline
          currentStep={pipelineStep}
          isRunning={agentPhase.phase !== 'idle' && agentPhase.phase !== 'complete'}
          scoreThreshold={70}
          mlScore={mlScore}
        />

        {/* Main Content Grid */}
        <div className="grid grid-cols-12 gap-6">

          {/* Left Column - Input Data */}
          <div className="col-span-4 space-y-4">
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="text-xl">📥</span> Input Data
                {isLoadingPnr && <span className="text-xs text-slate-400">(Loading...)</span>}
                {pipelineStep > 0 && pipelineStep < 6 && (
                  <span className="text-xs text-cyan-400 animate-pulse">(Loading from pipeline...)</span>
                )}
              </h2>

              {/* Customer Card - appears at step 3 (Passengers) */}
              {showCustomerData && customer ? (
                <div className={`rounded-xl p-4 mb-3 border transition-all duration-500 animate-fadeIn ${TIER_BG[customer.loyalty_tier] || TIER_BG['N']}`}>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-12 h-12 bg-slate-600 rounded-full flex items-center justify-center text-xl">
                      👤
                    </div>
                    <div>
                      <div className="font-semibold">{customer.name}</div>
                      <div className={`text-sm ${TIER_COLORS[customer.loyalty_tier] || TIER_COLORS['N']}`}>
                        {TIER_NAMES[customer.loyalty_tier] || 'General'} Member
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-slate-900/50 rounded-lg p-2">
                      <div className="text-slate-400 text-xs">Annual Revenue</div>
                      <div className="font-semibold">${customer.flight_revenue_amt_history?.toLocaleString() || 0}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-2">
                      <div className="text-slate-400 text-xs">Accept Rate</div>
                      <div className="font-semibold">
                        {customer.historical_upgrades?.acceptance_rate
                          ? `${(customer.historical_upgrades.acceptance_rate * 100).toFixed(0)}%`
                          : 'N/A'}
                      </div>
                    </div>
                  </div>
                  {customer.is_suppressed && (
                    <div className="mt-2 bg-red-900/30 border border-red-500/50 rounded-lg p-2 text-sm">
                      <span className="text-red-400">⚠️ Suppressed:</span>{' '}
                      <span className="text-red-200">{customer.complaint_reason || 'Customer preference'}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl p-4 mb-3 border border-slate-600 bg-slate-800/50">
                  <div className="text-slate-400 text-center flex items-center justify-center gap-2">
                    {pipelineStep > 0 && pipelineStep < 3 ? (
                      <>
                        <span className="animate-spin">⏳</span>
                        <span>Waiting for passenger data (Step 3)...</span>
                      </>
                    ) : (
                      <span>👤 Customer data appears at Step 3</span>
                    )}
                  </div>
                </div>
              )}

              {/* Flight Card - appears at step 1 (Eligible Flights) */}
              {showFlightData && flight ? (
                <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-4 mb-3 transition-all duration-500 animate-fadeIn">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">✈️</div>
                      <div>
                        <div className="font-semibold">AA{flight.operat_flight_nbr}</div>
                        <div className="text-blue-300">{flight.route}</div>
                      </div>
                    </div>
                    <div className={`text-[10px] px-2 py-0.5 rounded ${
                      estimatedLDF < 85
                        ? 'bg-emerald-900/50 text-emerald-300'
                        : 'bg-slate-700 text-slate-400'
                    }`}>
                      {estimatedLDF < 85 ? '✓ Proactive OK' : '✗ High LDF'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-slate-900/50 rounded-lg p-2">
                      <div className="text-slate-400 text-xs">Departure</div>
                      <div className="font-semibold">{reservation?.hours_to_departure || 0}h away</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-2">
                      <div className="text-slate-400 text-xs">Current Cabin</div>
                      <div className="font-semibold">
                        {reservation?.max_bkd_cabin_cd === 'F' ? 'Business' :
                         reservation?.max_bkd_cabin_cd === 'W' ? 'Premium Economy' : 'Economy'}
                      </div>
                    </div>
                  </div>
                  {/* LDF Indicator */}
                  <div className="mt-2 bg-slate-900/50 rounded-lg p-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-slate-400 text-xs">Est. Load Factor (LDF)</span>
                      <span className={`text-xs font-medium ${
                        estimatedLDF < 70 ? 'text-emerald-400' :
                        estimatedLDF < 85 ? 'text-amber-400' : 'text-red-400'
                      }`}>
                        {estimatedLDF}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all ${
                          estimatedLDF < 70 ? 'bg-emerald-500' :
                          estimatedLDF < 85 ? 'bg-amber-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${estimatedLDF}%` }}
                      />
                    </div>
                  </div>
                  {/* Cabin Availability */}
                  {flight.cabins && (
                    <div className="mt-2 flex gap-2 flex-wrap">
                      {Object.entries(flight.cabins).map(([cabin, data]) => (
                        <div key={cabin} className="bg-slate-900/50 rounded px-2 py-1 text-xs">
                          <span className="text-slate-400">{cabin}:</span>{' '}
                          <span className="text-emerald-400">{data.cabin_available} seats</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-4 mb-3">
                  <div className="text-slate-400 text-center flex items-center justify-center gap-2">
                    <span>✈️ Flight data appears at Step 1</span>
                  </div>
                </div>
              )}

              {/* ML Score Card - appears at step 4 */}
              {showMLScore && enrichedData?.ml_scores ? (
                <div className="bg-purple-900/20 border border-purple-500/30 rounded-xl p-4 mb-3 transition-all duration-500 animate-fadeIn">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">🤖</span>
                    <span className="font-semibold">ML Scores</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    {Object.entries((enrichedData.ml_scores as any).propensity_scores || {}).slice(0, 3).map(([offerType, data]: [string, any]) => (
                      <div key={offerType} className="bg-slate-900/50 rounded-lg p-2 text-center">
                        <div className="text-slate-400 text-[10px]">{offerType.replace('IU_', '')}</div>
                        <div className={`text-lg font-bold ${
                          data.confidence > 0.85 ? 'text-emerald-400' :
                          data.confidence > 0.6 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {(data.confidence * 100).toFixed(0)}%
                        </div>
                        <div className="text-[10px] text-slate-500">confidence</div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 text-xs text-purple-300">
                    Price Sensitivity: <span className="font-semibold">{String((enrichedData.ml_scores as any).price_sensitivity || 'medium')}</span>
                  </div>
                </div>
              ) : showMLScore ? (
                <div className="bg-purple-900/20 border border-purple-500/30 rounded-xl p-4 mb-3">
                  <div className="text-slate-400 text-center flex items-center justify-center gap-2">
                    <span className="animate-spin">⏳</span>
                    <span>Loading ML scores...</span>
                  </div>
                </div>
              ) : pipelineStep > 0 ? (
                <div className="bg-purple-900/20 border border-purple-500/30 rounded-xl p-4 mb-3">
                  <div className="text-slate-400 text-center">
                    <span>🤖 ML scores appear at Step 4</span>
                  </div>
                </div>
              ) : null}

              {/* Suppression Status Card - appears at step 5 (Policy) */}
              {showEligibility && customer ? (
                <div className={`rounded-xl p-3 mb-3 border transition-all duration-500 animate-fadeIn ${
                  customer.is_suppressed
                    ? 'bg-red-900/20 border-red-500/30'
                    : 'bg-emerald-900/20 border-emerald-500/30'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🛡️</span>
                      <span className="text-sm font-medium">Eligibility Check</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      customer.is_suppressed
                        ? 'bg-red-900/50 text-red-300'
                        : 'bg-emerald-900/50 text-emerald-300'
                    }`}>
                      {customer.is_suppressed ? '⚠️ Suppressed' : '✓ Eligible'}
                    </span>
                  </div>
                </div>
              ) : pipelineStep > 0 && pipelineStep < 5 ? (
                <div className="rounded-xl p-3 mb-3 border border-slate-600 bg-slate-800/50">
                  <div className="text-slate-400 text-center">
                    <span>🛡️ Eligibility check at Step 5</span>
                  </div>
                </div>
              ) : null}

              {/* Pre-flight Agent Results */}
              {preFlightAgents.length > 0 && (
                <div className="bg-cyan-900/20 border border-cyan-500/30 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">🤖</span>
                    <span className="font-semibold">Pre-flight Analysis</span>
                  </div>
                  <div className="space-y-2">
                    {preFlightAgents.map(agent => (
                      <div key={agent.agent_id} className="bg-slate-900/50 rounded-lg p-2">
                        <div className="text-xs text-cyan-400">{agent.agent_name}</div>
                        <div className="text-sm">{agent.summary}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Middle Column - Agent Reasoning */}
          <div className="col-span-5 space-y-4">
            <div data-tour="agent-reasoning" className="bg-slate-800/50 rounded-2xl p-5 border border-cyan-500/30 min-h-[500px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <span className="text-xl">🧠</span> Agent Reasoning
                  <span className="text-[10px] bg-cyan-600 text-white px-2 py-0.5 rounded-full font-bold">
                    PILLARS 1-2: TRANSPARENCY
                  </span>
                </h2>
                <span className="text-xs text-cyan-400 bg-cyan-900/50 px-2 py-1 rounded flex items-center gap-1">
                  <span className="animate-pulse">💭</span> See the WHY
                </span>
              </div>
              <div className="text-[10px] text-slate-400 mb-4 -mt-2">
                Watch the agent THINK, not just score • Plan → Execute → Decide
              </div>

              {/* Phase Indicators */}
              <div className="flex items-center justify-between mb-6">
                {[
                  { id: 'planner', label: 'Planner', icon: '📋', desc: 'What to check?' },
                  { id: 'worker', label: 'Worker', icon: '🔍', desc: 'Execute checks' },
                  { id: 'solver', label: 'Solver', icon: '✅', desc: 'Final decision' },
                ].map((phase, idx) => (
                  <div key={phase.id} className="flex items-center">
                    <div className={`flex flex-col items-center transition-all duration-300 ${
                      agentPhase.phase === phase.id ? 'scale-110' : ''
                    }`}>
                      <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-2xl transition-all ${
                        agentPhase.phase === phase.id
                          ? 'bg-cyan-600 shadow-lg shadow-cyan-500/30 animate-pulse'
                          : agentPhase.phase === 'complete' ||
                            (phase.id === 'planner' && ['worker', 'solver', 'complete'].includes(agentPhase.phase)) ||
                            (phase.id === 'worker' && ['solver', 'complete'].includes(agentPhase.phase))
                            ? 'bg-emerald-600'
                            : 'bg-slate-700'
                      }`}>
                        {phase.icon}
                      </div>
                      <div className={`text-xs mt-2 font-medium ${
                        agentPhase.phase === phase.id ? 'text-cyan-300' : 'text-slate-400'
                      }`}>
                        {phase.label}
                      </div>
                      <div className="text-[10px] text-slate-500">{phase.desc}</div>
                    </div>
                    {idx < 2 && (
                      <div className={`w-12 h-0.5 mx-2 transition-all ${
                        (idx === 0 && ['worker', 'solver', 'complete'].includes(agentPhase.phase)) ||
                        (idx === 1 && ['solver', 'complete'].includes(agentPhase.phase))
                          ? 'bg-emerald-500'
                          : 'bg-slate-600'
                      }`} />
                    )}
                  </div>
                ))}
              </div>

              {/* Thinking Display */}
              <div className="space-y-4">
                {/* Planner Thought */}
                {(agentPhase.phase === 'planner' || ['worker', 'solver', 'complete'].includes(agentPhase.phase)) && plannerThought && (
                  <div data-tour="planner-section" className="bg-slate-900/50 rounded-xl p-4 border border-cyan-500/30">
                    <div className="text-xs text-cyan-400 mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>📋</span> PLANNER
                      </div>
                      <span className="text-[10px] bg-cyan-600 text-white px-2 py-0.5 rounded-full font-bold">
                        PILLAR 1: PLANNING
                      </span>
                    </div>
                    <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans">
                      {plannerThought}
                    </pre>
                  </div>
                )}

                {/* Worker Evaluations */}
                {['worker', 'solver', 'complete'].includes(agentPhase.phase) && evaluations.length > 0 && (
                  <div data-tour="worker-section" className="bg-slate-900/50 rounded-xl p-4 border border-purple-500/30">
                    <div className="text-xs text-purple-400 mb-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>⚙️</span> WORKER EVALUATIONS
                      </div>
                    </div>
                    <div className="space-y-2">
                      {evaluations.map((evaluation, idx) => (
                        <div
                          key={idx}
                          className={`flex items-start gap-3 p-2 rounded-lg transition-all ${
                            evaluation.status === 'running'
                              ? 'bg-purple-900/30 border border-purple-500/50'
                              : evaluation.status === 'complete'
                                ? 'bg-emerald-900/20 border border-emerald-500/30'
                                : 'bg-slate-800/50 border border-slate-600'
                          }`}
                        >
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
                            evaluation.status === 'running'
                              ? 'bg-purple-600 animate-spin'
                              : evaluation.status === 'complete'
                                ? 'bg-emerald-600'
                                : 'bg-slate-600'
                          }`}>
                            {evaluation.status === 'complete' ? '✓' : evaluation.status === 'running' ? '◌' : idx + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">{evaluation.type}</div>
                            {evaluation.recommendation && (
                              <div className="text-xs text-emerald-300 mt-1">
                                {evaluation.recommendation}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Solver Thought */}
                {['solver', 'complete'].includes(agentPhase.phase) && solverThought && (
                  <div data-tour="solver-section" className="bg-slate-900/50 rounded-xl p-4 border border-emerald-500/30">
                    <div className="text-xs text-emerald-400 mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>✅</span> SOLVER
                      </div>
                      <span className="text-[10px] bg-purple-600 text-white px-2 py-0.5 rounded-full font-bold">
                        PILLAR 2: REASONING
                      </span>
                    </div>
                    <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans">
                      {solverThought}
                    </pre>
                    <div className="mt-2 pt-2 border-t border-slate-700 text-[10px] text-purple-300">
                      👁️ Full audit trail - every factor, every reason, every decision explained
                    </div>
                  </div>
                )}

                {/* Idle State - Show 4 Pillars */}
                {agentPhase.phase === 'idle' && (
                  <div className="space-y-4">
                    {/* Why Agentic AI Header */}
                    <div className="text-center py-2">
                      <h3 className="text-lg font-bold text-white mb-1">Why Agentic AI?</h3>
                      <p className="text-xs text-slate-400">What makes this different from traditional ML + Rules</p>
                    </div>

                    {/* 4 Pillars Grid */}
                    <div data-tour="pillars-grid" className="grid grid-cols-4 gap-3">
                      {[
                        { num: 1, label: 'PLANNING', desc: 'Agent thinks first', color: 'cyan', icon: '📋' },
                        { num: 2, label: 'REASONING', desc: 'Full transparency', color: 'purple', icon: '🧠' },
                        { num: 3, label: 'BUSINESS CONTROL', desc: 'You drive it', color: 'amber', icon: '🎛️' },
                        { num: 4, label: 'HUMAN + AI', desc: 'You stay in charge', color: 'emerald', icon: '🤝' },
                      ].map((pillar) => (
                        <div
                          key={pillar.num}
                          className={`p-3 rounded-lg border text-center transition-all hover:scale-105 ${
                            pillar.color === 'cyan' ? 'bg-cyan-900/30 border-cyan-500/50' :
                            pillar.color === 'purple' ? 'bg-purple-900/30 border-purple-500/50' :
                            pillar.color === 'amber' ? 'bg-amber-900/30 border-amber-500/50' :
                            'bg-emerald-900/30 border-emerald-500/50'
                          }`}
                        >
                          <div className="text-2xl mb-1">{pillar.icon}</div>
                          <div className={`text-[10px] font-bold ${
                            pillar.color === 'cyan' ? 'text-cyan-400' :
                            pillar.color === 'purple' ? 'text-purple-400' :
                            pillar.color === 'amber' ? 'text-amber-400' :
                            'text-emerald-400'
                          }`}>
                            P{pillar.num}: {pillar.label}
                          </div>
                          <div className="text-[9px] text-slate-500 mt-0.5">{pillar.desc}</div>
                        </div>
                      ))}
                    </div>

                    {/* CTA */}
                    <div className="text-center pt-4 border-t border-slate-700">
                      <div className="text-2xl mb-2">🎯</div>
                      <div className="text-sm text-slate-300">Click <span className="text-emerald-400 font-semibold">"Run Agent"</span> to see pillars in action</div>
                      <div className="text-xs text-slate-500 mt-1">Watch the agent THINK through a real decision</div>
                    </div>
                  </div>
                )}

                {/* Loading State */}
                {agentPhase.phase === 'loading' && (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                    <div className="text-4xl mb-4 animate-bounce">⏳</div>
                    <div className="text-lg">Running pre-flight agents...</div>
                    <div className="text-sm mt-2">Customer Intelligence • Flight Optimization</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Decision & Config */}
          <div className="col-span-3 space-y-4">
            {/* Final Decision */}
            <div data-tour="final-decision" className={`bg-slate-800/50 rounded-2xl p-5 border transition-all duration-500 ${
              showingDecision
                ? finalDecision?.offerType === 'REJECTED' || finalDecision?.offerType === 'SUPPRESSED'
                  ? 'border-red-500 shadow-lg shadow-red-500/20'
                  : 'border-emerald-500 shadow-lg shadow-emerald-500/20'
                : hitlPending
                  ? 'border-amber-500 shadow-lg shadow-amber-500/20'
                  : 'border-slate-700'
            }`}>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="text-xl">🎯</span> Final Decision
                {hitlPending && (
                  <>
                    <span className="text-xs bg-amber-500 text-black px-2 py-0.5 rounded-full animate-pulse">
                      AWAITING APPROVAL
                    </span>
                    <span className="text-[10px] bg-emerald-600 text-white px-2 py-0.5 rounded-full font-bold">
                      PILLAR 4: HUMAN + AI
                    </span>
                  </>
                )}
              </h2>

              {/* HITL Pending Approval */}
              {hitlPending && pendingDecision && (
                <div className="space-y-3">
                  <div className="bg-amber-900/30 border border-amber-500/50 rounded-xl p-4 text-center">
                    <div className="text-amber-400 text-sm mb-1">PENDING APPROVAL</div>
                    <div className="text-2xl font-bold text-white">{pendingDecision.offerName}</div>
                    <div className="text-3xl font-bold text-amber-400 mt-2">
                      ${pendingDecision.price.toFixed(0)}
                      {pendingDecision.discount > 0 && (
                        <span className="text-sm text-amber-300 ml-2">
                          (-{pendingDecision.discount}%)
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Expected Value</div>
                      <div className="text-lg font-bold text-cyan-400">
                        ${pendingDecision.expectedValue.toFixed(2)}
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Confidence</div>
                      <div className="text-lg font-bold text-emerald-400">
                        {pendingDecision.confidence}
                      </div>
                    </div>
                  </div>

                  {/* HITL Action Buttons */}
                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={handleApprove}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                      <span>✅</span> Approve
                    </button>
                    <button
                      onClick={handleReject}
                      className="flex-1 bg-red-600 hover:bg-red-500 text-white font-medium py-3 rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                      <span>❌</span> Reject
                    </button>
                  </div>
                </div>
              )}

              {/* Approved/Final Decision */}
              {finalDecision && showingDecision && (
                <div className="space-y-3">
                  <div className={`rounded-xl p-4 text-center ${
                    finalDecision.offerType === 'REJECTED'
                      ? 'bg-red-900/30 border border-red-500/50'
                      : finalDecision.offerType === 'SUPPRESSED'
                        ? 'bg-slate-900/50 border border-slate-500/50'
                        : 'bg-emerald-900/30 border border-emerald-500/50'
                  }`}>
                    <div className={`text-sm mb-1 ${
                      finalDecision.offerType === 'REJECTED' ? 'text-red-400'
                        : finalDecision.offerType === 'SUPPRESSED' ? 'text-slate-400'
                        : 'text-emerald-400'
                    }`}>
                      {finalDecision.offerType === 'REJECTED' ? 'REJECTED'
                        : finalDecision.offerType === 'SUPPRESSED' ? 'NO OFFER'
                        : hitlEnabled ? 'APPROVED' : 'RECOMMENDED'}
                    </div>
                    <div className="text-2xl font-bold text-white">{finalDecision.offerName}</div>
                    {finalDecision.price > 0 && (
                      <div className="text-3xl font-bold text-emerald-400 mt-2">
                        ${finalDecision.price.toFixed(0)}
                        {finalDecision.discount > 0 && (
                          <span className="text-sm text-amber-400 ml-2">
                            (-{finalDecision.discount}%)
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {finalDecision.price > 0 && (
                    <>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-slate-400">Expected Value</div>
                          <div className="text-lg font-bold text-cyan-400">
                            ${finalDecision.expectedValue.toFixed(2)}
                          </div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-slate-400">Confidence</div>
                          <div className={`text-lg font-bold ${
                            finalDecision.confidence === 'HIGH' ? 'text-emerald-400' : 'text-amber-400'
                          }`}>
                            {finalDecision.confidence}
                          </div>
                        </div>
                      </div>

                      <div className="bg-slate-900/50 rounded-lg p-3">
                        <div className="text-xs text-slate-400 mb-1">Channel</div>
                        <div className="text-sm font-medium">{finalDecision.channel} Notification</div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Waiting State */}
              {!finalDecision && !hitlPending && (
                <div className="flex flex-col items-center justify-center h-40 text-slate-500">
                  <div className="text-3xl mb-2">⏳</div>
                  <div className="text-sm">Waiting for agent decision...</div>
                </div>
              )}
            </div>

          </div>
        </div>
      </div>

      {/* Explainer Video Modal */}
      <ExplainerVideo />
      <PromptAssistant
        isOpen={promptAssistantOpen}
        onOpenChange={setPromptAssistantOpen}
      />

      {/* Guided Demo - Voice-narrated tour */}
      <GuidedDemo
        onSelectCustomer={(pnr) => setSelectedPNR(pnr)}
        onRunAgent={runAgent}
        onToggleHITL={setHitlEnabled}
        onExpandControlPanel={setShowControlPanel}
        onToggleAdvancedMode={setAdvancedMode}
        onOpenPromptAssistant={() => setPromptAssistantOpen(true)}
        isAgentComplete={agentPhase.phase === 'complete' && !hitlPending}
        availablePNRs={pnrList.map(p => p.pnr)}
        // Dynamic data for contextual narration
        customerInfo={customer ? {
          name: customer.name,
          loyalty_tier: customer.loyalty_tier,
          flight_revenue_amt_history: customer.flight_revenue_amt_history,
          aadv_tenure_days: customer.aadv_tenure_days,
        } : undefined}
        plannerInfo={guidedDemoPlannerInfo || undefined}
        workerInfo={guidedDemoWorkerInfo || undefined}
        solverInfo={guidedDemoSolverInfo || undefined}
      />
    </div>
  );
}

// Decision Pipeline Component
function DecisionPipeline({
  currentStep,
  isRunning,
  scoreThreshold,
  mlScore,
}: {
  currentStep: number;
  isRunning: boolean;
  scoreThreshold: number;
  mlScore: number;
}) {
  const steps = [
    { id: 1, icon: '✈️', label: 'Eligible Flights', desc: 'Flights with inventory' },
    { id: 2, icon: '📋', label: 'PNRs', desc: 'Reservation records' },
    { id: 3, icon: '👥', label: 'Passengers', desc: 'Individual travelers' },
    { id: 4, icon: '🤖', label: 'ML Score', desc: 'Propensity prediction', highlight: true },
    { id: 5, icon: '📜', label: 'Policy', desc: 'Business rules', highlight: true },
    { id: 6, icon: '🎯', label: 'Decision', desc: 'Send or suppress' },
  ];

  const passesThreshold = mlScore * 100 >= scoreThreshold;

  return (
    <div className="bg-slate-800/30 rounded-xl p-4 mb-6 border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Decision Pipeline</span>
          <span className="text-xs px-2 py-0.5 rounded bg-cyan-900/50 text-cyan-300">
            Real Backend
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between">
        {steps.map((step, idx) => (
          <div key={step.id} className="flex items-center flex-1">
            <div className={`flex flex-col items-center transition-all duration-300 ${
              currentStep >= step.id ? 'scale-105' : ''
            }`}>
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center text-xl transition-all relative ${
                currentStep === step.id && isRunning
                  ? step.id === 4 ? 'bg-purple-600 shadow-lg shadow-purple-500/30 animate-pulse'
                    : step.id === 5 ? 'bg-amber-600 shadow-lg shadow-amber-500/30 animate-pulse'
                    : 'bg-cyan-600 shadow-lg shadow-cyan-500/30 animate-pulse'
                  : currentStep > step.id
                    ? 'bg-emerald-600/80'
                    : step.id === 4 ? 'bg-purple-900/50 border border-purple-500/30'
                    : step.id === 5 ? 'bg-amber-900/50 border border-amber-500/30'
                    : 'bg-slate-700/50'
              }`}>
                {step.icon}
                {currentStep > step.id && (
                  <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center text-xs">
                    ✓
                  </div>
                )}
              </div>
              <div className={`text-xs mt-2 font-medium text-center ${
                currentStep >= step.id ? 'text-white' : 'text-slate-500'
              }`}>
                {step.label}
              </div>
              <div className="text-[10px] text-slate-500 text-center">{step.desc}</div>

              {step.id === 4 && currentStep >= 4 && (
                <div className="mt-2 px-2 py-1 bg-purple-900/50 rounded text-xs">
                  Score: <span className="text-purple-300 font-mono">{(mlScore * 100).toFixed(0)}%</span>
                </div>
              )}

              {step.id === 5 && currentStep >= 5 && (
                <div className="mt-2 px-2 py-1 bg-amber-900/50 rounded text-xs">
                  Threshold: <span className="text-amber-300 font-mono">{scoreThreshold}%</span>
                </div>
              )}

              {step.id === 6 && currentStep >= 6 && (
                <div className={`mt-2 px-2 py-1 rounded text-xs font-medium ${
                  passesThreshold ? 'bg-emerald-900/50 text-emerald-300' : 'bg-red-900/50 text-red-300'
                }`}>
                  {passesThreshold ? 'SEND' : 'SUPPRESS'}
                </div>
              )}
            </div>

            {idx < steps.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 transition-all relative ${
                currentStep > step.id ? 'bg-emerald-500' : 'bg-slate-600'
              }`}>
                {currentStep > step.id && (
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 border-r-2 border-t-2 border-emerald-500 rotate-45"></div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {currentStep === 0 && (
        <div className="mt-4 text-center text-sm text-slate-400">
          Click "Run Agent" to see the decision pipeline in action
        </div>
      )}
    </div>
  );
}
