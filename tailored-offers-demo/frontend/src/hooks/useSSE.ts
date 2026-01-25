import { useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface HITLResult {
  status: string;
  approval_request_id?: string;
  approval_reason?: string;
  approval_reason_details?: string;
  proposed_offer?: {
    offer_type: string;
    price: number;
    discount_percent?: number;
    expected_value?: number;
  };
  escalation_reasons?: string[];
  final_decision?: any;
  suppression_reason?: string;
}

type ExecutionMode = 'choreography' | 'planner-worker';

// ReWOO-specific event types
interface ReWOOPlanStep {
  step_id: string;
  evaluation_type: string;
  description: string;
}

interface ReWOOWorkerStep {
  step_id: string;
  evaluation_type: string;
  recommendation: string;
  reasoning: string;
}

interface ReWOODecision {
  selected_offer: string;
  offer_price: number;
  discount_applied: number;
  expected_value: number;
  reasoning: string;
  policies_applied: string[];
  should_send_offer: boolean;
}

interface SSECallbacks {
  onPipelineStart?: (data: { pnr: string; total_steps: number; execution_mode?: string }) => void;
  onPlannerStart?: (data: { message: string }) => void;
  onPlannerDecision?: (data: { plan: string[]; reasoning: string }) => void;
  onAgentStart?: (data: { agent_id: string; agent_name: string; step: number }) => void;
  onAgentComplete?: (data: {
    agent_id: string;
    agent_name: string;
    step: number;
    status: string;
    duration_ms: number;
    summary: string;
    reasoning: string;
    outputs: Record<string, any>;
  }) => void;
  onAgentSkip?: (data: { agent_id: string; agent_name: string; step: number; reason: string }) => void;
  onPipelineComplete?: (data: {
    success: boolean;
    final_decision: any;
    total_duration_ms: number;
  }) => void;
  onError?: (error: string) => void;
  // New ReWOO-specific callbacks
  onReWOOPlannerComplete?: (data: {
    plan: ReWOOPlanStep[];
    reasoning: string;
    offer_options: any[];
  }) => void;
  onReWOOWorkerStep?: (data: ReWOOWorkerStep) => void;
  onReWOOSolverComplete?: (data: { decision: ReWOODecision }) => void;
}

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);

  const startEvaluation = useCallback((pnr: string, callbacks: SSECallbacks, executionMode: ExecutionMode = 'choreography') => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_BASE}/api/pnrs/${pnr}/evaluate?execution_mode=${executionMode}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('pipeline_start', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onPipelineStart?.(data);
    });

    // Planner-worker specific events
    eventSource.addEventListener('planner_start', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onPlannerStart?.(data);
    });

    eventSource.addEventListener('planner_decision', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onPlannerDecision?.(data);
    });

    eventSource.addEventListener('agent_start', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onAgentStart?.(data);
    });

    eventSource.addEventListener('agent_complete', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onAgentComplete?.(data);
    });

    eventSource.addEventListener('agent_skip', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onAgentSkip?.(data);
    });

    // ReWOO-specific events for Offer Orchestration
    eventSource.addEventListener('rewoo_planner_complete', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onReWOOPlannerComplete?.(data);
    });

    eventSource.addEventListener('rewoo_worker_step', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onReWOOWorkerStep?.(data);
    });

    eventSource.addEventListener('rewoo_solver_complete', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onReWOOSolverComplete?.(data);
    });

    eventSource.addEventListener('pipeline_complete', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onPipelineComplete?.(data);
      eventSource.close();
    });

    eventSource.addEventListener('error', (event) => {
      const data = JSON.parse((event as MessageEvent).data || '{}');
      callbacks.onError?.(data.error || 'Unknown error');
      eventSource.close();
    });

    eventSource.onerror = () => {
      callbacks.onError?.('Connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const stopEvaluation = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  /**
   * Start evaluation with Human-in-the-Loop support.
   * This is a direct API call (not SSE) that may return a pending approval.
   */
  const startEvaluationHITL = useCallback(async (pnr: string, forceApproval: boolean = false): Promise<HITLResult> => {
    const url = `${API_BASE}/api/pnrs/${pnr}/evaluate-hitl?force_approval=${forceApproval}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HITL evaluation failed: ${response.statusText}`);
    }

    return response.json();
  }, []);

  return { startEvaluation, stopEvaluation, startEvaluationHITL };
}
