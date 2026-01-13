import { useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SSECallbacks {
  onPipelineStart?: (data: { pnr: string; total_steps: number }) => void;
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
}

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);

  const startEvaluation = useCallback((pnr: string, callbacks: SSECallbacks) => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_BASE}/api/pnrs/${pnr}/evaluate`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('pipeline_start', (event) => {
      const data = JSON.parse(event.data);
      callbacks.onPipelineStart?.(data);
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

  return { startEvaluation, stopEvaluation };
}
