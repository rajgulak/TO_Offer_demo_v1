/**
 * Parse Offer Reasoning
 *
 * Utility to parse the `offer_reasoning` text from the backend's
 * offer_orchestration agent and extract structured information.
 *
 * The backend reasoning follows the ReWOO pattern:
 * - STEP 1: PLANNER (Making a Plan)
 * - STEP 2: WORKER (Doing the Checks)
 * - STEP 3: SOLVER (Making the Final Decision)
 */

import type { ParsedOfferReasoning, ParsedEvaluationStep } from '../types/backend';

/**
 * Parse the offer_reasoning text from the backend
 */
export function parseOfferReasoning(reasoning: string): ParsedOfferReasoning {
  if (!reasoning) {
    return {
      plannerThoughts: '',
      evaluationSteps: [],
      solverThoughts: '',
    };
  }

  // Split by the major sections
  const plannerMatch = reasoning.match(/STEP 1: PLANNER.*?(?==+ *STEP 2|$)/s);
  const workerMatch = reasoning.match(/STEP 2: WORKER.*?(?==+ *STEP 3|$)/s);
  const solverMatch = reasoning.match(/STEP 3: SOLVER.*$/s);

  // Extract planner thoughts
  let plannerThoughts = '';
  if (plannerMatch) {
    plannerThoughts = cleanSection(plannerMatch[0]);
  }

  // Extract worker evaluation steps
  const evaluationSteps: ParsedEvaluationStep[] = [];
  if (workerMatch) {
    const workerSection = workerMatch[0];

    // Find all "--- Executing E#: TYPE ---" blocks
    const stepRegex = /--- Executing (E\d+): (\w+) ---\s*([\s\S]*?)(?=--- Executing|STEP 3|$)/g;
    let match;

    while ((match = stepRegex.exec(workerSection)) !== null) {
      const stepId = match[1];
      const evaluationType = match[2];
      const content = match[3].trim();

      // Parse the content for recommendation
      const recMatch = content.match(/([✓⚠️⚡💰📦].*)/);

      evaluationSteps.push({
        stepId,
        evaluationType,
        description: getEvaluationDescription(evaluationType),
        result: content,
        recommendation: recMatch ? recMatch[1] : undefined,
      });
    }
  }

  // Extract solver thoughts
  let solverThoughts = '';
  let synthesis = '';
  let finalDecision = '';

  if (solverMatch) {
    const solverSection = solverMatch[0];
    solverThoughts = cleanSection(solverSection);

    // Extract synthesis
    const synthMatch = solverSection.match(/SYNTHESIS:\s*(.+?)(?=\n\n|✅|$)/s);
    if (synthMatch) {
      synthesis = synthMatch[1].trim();
    }

    // Extract final decision
    const decisionMatch = solverSection.match(/✅ FINAL DECISION:\s*(.+?)(?=\n\s*Discount|\n\s*Expected|$)/s);
    if (decisionMatch) {
      finalDecision = decisionMatch[1].trim();
    }
  }

  return {
    plannerThoughts,
    evaluationSteps,
    solverThoughts,
    synthesis,
    finalDecision,
  };
}

/**
 * Clean a section by removing separator lines
 */
function cleanSection(text: string): string {
  return text
    .replace(/=+/g, '')
    .replace(/STEP \d+: \w+.*?\n/g, '')
    .replace(/\(.*?\)/g, '')
    .trim();
}

/**
 * Get a human-readable description for an evaluation type
 */
function getEvaluationDescription(evaluationType: string): string {
  const descriptions: Record<string, string> = {
    CONFIDENCE: 'Check ML confidence levels for each offer',
    RELATIONSHIP: 'Check for recent customer service issues',
    PRICE_SENSITIVITY: 'Evaluate customer price sensitivity',
    INVENTORY: 'Check cabin inventory priority',
    EV_COMPARISON: 'Calculate expected values for each offer',
  };
  return descriptions[evaluationType] || `Evaluate ${evaluationType}`;
}

/**
 * Map backend final decision to frontend display format
 */
export function mapToFinalDecision(backendDecision: {
  should_send_offer: boolean;
  offer_type?: string;
  price?: number;
  discount_percent?: number;
  channel?: string;
  message_body?: string;
  suppression_reason?: string;
}): {
  offerType: string;
  offerName: string;
  price: number;
  discount: number;
  expectedValue: number;
  confidence: string;
  channel: string;
  reasoning: string;
} {
  if (!backendDecision.should_send_offer) {
    return {
      offerType: 'SUPPRESSED',
      offerName: `No Offer (${backendDecision.suppression_reason || 'Criteria not met'})`,
      price: 0,
      discount: 0,
      expectedValue: 0,
      confidence: 'N/A',
      channel: 'N/A',
      reasoning: backendDecision.suppression_reason || 'Customer did not meet offer criteria',
    };
  }

  const offerNames: Record<string, string> = {
    'IU_BUSINESS': 'Business Class Upgrade',
    'IU_PREMIUM_ECONOMY': 'Premium Economy Upgrade',
    'MCE': 'Main Cabin Extra',
  };

  const offerType = backendDecision.offer_type || 'UNKNOWN';
  const price = backendDecision.price || 0;
  const discount = backendDecision.discount_percent || 0;

  // Estimate EV (p_buy is not returned, so we estimate)
  const estimatedPBuy = 0.3;
  const margin = 0.85;
  const expectedValue = estimatedPBuy * price * margin;

  return {
    offerType,
    offerName: offerNames[offerType] || offerType,
    price,
    discount,
    expectedValue,
    confidence: discount > 0 ? 'MEDIUM' : 'HIGH',
    channel: backendDecision.channel || 'Push',
    reasoning: backendDecision.message_body || `Recommended ${offerNames[offerType] || offerType} at $${price}`,
  };
}

/**
 * Parse pre-flight agent outputs into display format
 */
export function parsePreFlightAgents(agentData: {
  agent_id: string;
  summary: string;
  reasoning: string;
  outputs: Record<string, unknown>;
}): {
  title: string;
  summary: string;
  details: string[];
} {
  const { agent_id, summary, outputs } = agentData;

  if (agent_id === 'customer_intelligence') {
    return {
      title: 'Customer Intelligence',
      summary,
      details: [
        `Eligible: ${outputs.customer_eligible ? 'Yes' : 'No'}`,
        `Segment: ${outputs.customer_segment || 'N/A'}`,
        outputs.suppression_reason ? `Suppression: ${outputs.suppression_reason}` : '',
      ].filter(Boolean),
    };
  }

  if (agent_id === 'flight_optimization') {
    return {
      title: 'Flight Optimization',
      summary,
      details: [
        `Priority: ${outputs.flight_priority || 'N/A'}`,
        `Recommended Cabins: ${(outputs.recommended_cabins as string[])?.join(', ') || 'None'}`,
      ],
    };
  }

  return {
    title: agent_id,
    summary,
    details: [],
  };
}
