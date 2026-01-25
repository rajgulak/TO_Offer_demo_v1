/**
 * Backend API Types for BusinessAgentDemo
 *
 * These types map to the actual API responses from the FastAPI backend.
 */

// Response from GET /api/pnrs
export interface PNRSummary {
  pnr: string;
  customer_name: string;
  customer_tier: string;
  route: string;
  hours_to_departure: number;
  scenario_tag: string;
}

// Customer profile from enriched PNR
export interface CustomerProfile {
  lylty_acct_id: string;
  name: string;
  loyalty_tier: string;  // E, T, P, G, etc.
  aadv_tenure_days: number;
  business_trip_likelihood: number;
  flight_revenue_amt_history: number;
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

// Flight info from enriched PNR
export interface FlightInfo {
  operat_flight_nbr: number;
  route: string;
  leg_dep_dt: string;
  schd_leg_dep_lcl_tms: string;
  equipment_model?: string;
  cabins: Record<string, CabinInfo>;
}

export interface CabinInfo {
  cabin_capacity: number;
  cabin_total_pax: number;
  cabin_available: number;
  expected_load_factor: number;
}

// Reservation info
export interface ReservationInfo {
  hours_to_departure: number;
  max_bkd_cabin_cd: string;  // F, W, Y
  fare_class: string;
  checked_in: boolean;
}

// Response from GET /api/pnrs/{pnr}
export interface EnrichedPNRResponse {
  pnr_locator: string;
  customer: CustomerProfile;
  flight: FlightInfo;
  reservation: ReservationInfo;
  ml_scores?: Record<string, MLScore>;
}

export interface MLScore {
  propensity_scores?: {
    [offerType: string]: {
      confidence: number;
      price_points?: {
        [price: string]: {
          p_buy: number;
        };
      };
    };
  };
  price_sensitivity?: 'low' | 'medium' | 'high';
}

// Parsed evaluation step from offer_reasoning
export interface ParsedEvaluationStep {
  stepId: string;
  evaluationType: string;
  description: string;
  result?: string;
  recommendation?: string;
}

// Parsed reasoning structure
export interface ParsedOfferReasoning {
  plannerThoughts: string;
  evaluationSteps: ParsedEvaluationStep[];
  solverThoughts: string;
  synthesis?: string;
  finalDecision?: string;
}

// Final decision from pipeline_complete event
export interface BackendFinalDecision {
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

// Agent complete event data
export interface AgentCompleteData {
  agent_id: string;
  agent_name: string;
  step: number;
  status: string;
  duration_ms: number;
  summary: string;
  reasoning: string;
  outputs: Record<string, unknown>;
}

// Pipeline complete event data
export interface PipelineCompleteData {
  success: boolean;
  final_decision: BackendFinalDecision;
  total_duration_ms: number;
  reasoning_trace?: string[];
}
