// PNR Types
export interface PNRSummary {
  pnr: string;
  customer_name: string;
  customer_tier: string;
  route: string;
  hours_to_departure: number;
  scenario_tag: string;
}

export interface CustomerData {
  customer_id: string;
  name: string;
  loyalty_tier: string;
  tenure_days: number;
  travel_pattern: string;
  annual_revenue: number;
  is_suppressed: boolean;
  complaint_reason?: string;
  marketing_consent?: {
    push: boolean;
    email: boolean;
  };
  historical_upgrades?: {
    acceptance_rate: number;
    offers_received: number;
  };
}

export interface FlightData {
  flight_id: string;
  route: string;
  departure_date: string;
  departure_time: string;
  aircraft_type?: string;
  cabins: Record<string, CabinData>;
}

export interface CabinData {
  total_seats: number;
  sold_seats: number;
  available_seats: number;
  load_factor: number;
  needs_treatment?: boolean;
}

export interface EnrichedPNR {
  pnr_locator: string;
  customer: CustomerData;
  flight: FlightData;
  reservation: {
    hours_to_departure: number;
    current_cabin: string;
    fare_class: string;
    checked_in: boolean;
  };
  ml_scores?: Record<string, any>;
}

// Agent Types
export type AgentStatus = 'pending' | 'processing' | 'complete' | 'skipped' | 'error';

export interface AgentConfig {
  id: string;
  name: string;
  short_name: string;
  icon: string;
  description: string;
}

export interface AgentResult {
  agent_id: string;
  agent_name: string;
  step: number;
  status: AgentStatus;
  duration_ms: number;
  summary: string;
  reasoning: string;
  outputs: Record<string, any>;
}

// Decision Types
export interface FinalDecision {
  should_send_offer: boolean;
  offer_type?: string;
  price?: number;
  discount_percent?: number;
  channel?: string;
  send_time?: string;
  message_subject?: string;
  message_body?: string;
  fallback_offer?: {
    offer_type: string;
    display_name: string;
    price: number;
  };
  experiment_group?: string;
  tracking_id?: string;
  suppression_reason?: string;
}

// SSE Event Types
export interface SSEAgentStart {
  agent_id: string;
  agent_name: string;
  step: number;
  total_steps: number;
}

export interface SSEAgentComplete {
  agent_id: string;
  agent_name: string;
  step: number;
  status: 'complete';
  duration_ms: number;
  summary: string;
  reasoning: string;
  outputs: Record<string, any>;
}

export interface SSEAgentSkip {
  agent_id: string;
  agent_name: string;
  step: number;
  reason: string;
}

export interface SSEPipelineComplete {
  success: boolean;
  final_decision: FinalDecision;
  total_duration_ms: number;
  reasoning_trace: string[];
}

// App State
export interface AppState {
  pnrList: PNRSummary[];
  selectedPNR: string | null;
  enrichedData: EnrichedPNR | null;
  pipelineStatus: 'idle' | 'running' | 'complete' | 'error';
  agentResults: Record<string, AgentResult>;
  currentAgentId: string | null;
  selectedAgentTab: string | null;
  finalDecision: FinalDecision | null;
  showMessagePreview: boolean;
}
