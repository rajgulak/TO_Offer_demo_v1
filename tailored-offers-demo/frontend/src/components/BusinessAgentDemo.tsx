/**
 * Business Agent Demo - Visual Showcase of Offer Agent Decision Making
 *
 * This component provides a self-explanatory, visually appealing demo
 * that shows how the Offer Agent makes decisions.
 *
 * How it works (in plain English):
 * - ML Service: The computer looks at customer data and predicts how likely they are to buy
 * - Offer Agent: Figures out which upgrade offer to give based on the predictions and business rules
 * - Channel: Decides the best way to send the offer (email, app, text message)
 * - Config: Business rules are in a simple config file (no code changes needed to adjust)
 * - Decision: For each passenger, "If the score is high enough, send them an offer"
 *
 * Key Features:
 * - Clear data input visualization
 * - Shows ML Score → Offer Agent Decision → Channel Selection flow
 * - Adjustable thresholds (business can tune without code changes)
 * - No technical jargon - business-friendly language
 */
import { useState, useEffect, useCallback } from 'react';

// Types
interface CustomerData {
  name: string;
  loyaltyTier: string;
  tierDisplay: string;
  annualRevenue: number;
  acceptanceRate: number;
  tenureDays: number;
  recentIssue?: { type: string; date: string };
  // Suppression-related fields
  lastContactedDays: number;  // Days since last marketing contact
  isDistressed: boolean;      // Currently experiencing travel disruption
}

interface FlightData {
  flightNumber: string;
  route: string;
  departureDate: string;
  hoursToDepart: number;
  currentCabin: string;
  availableSeats: { [key: string]: number };
  // Flight LDF (Load Factor) estimation - determines if flight needs proactive treatment
  estimatedLDF: number;       // 0-100% estimated final load factor
  needsProactiveTreatment: boolean;  // True if flight has excess inventory to fill
}

interface MLScores {
  businessProb: number;
  businessConf: number;
  premiumProb: number;
  premiumConf: number;
  mceProb: number;
  mceConf: number;
}

interface PricingData {
  businessBase: number;
  premiumBase: number;
  mceBase: number;
}

interface DecisionVariables {
  minConfidence: number;
  maxDiscount: number;
  minExpectedValue: number;
  vipRevenueThreshold: number;
  goodwillDiscountPercent: number;
  // Sendout timing (from PDF: 72/48/24 hrs before departure)
  sendoutTiming: 72 | 48 | 24;
  // Suppression rules
  minDaysSinceContact: number;  // Don't contact if contacted within X days
  suppressDistressed: boolean;   // Don't send offers to distressed customers
  // Flight LDF threshold
  minLDFForProactive: number;   // Only proactively offer if LDF below this %
}

// Ranking Mode: Customer-level (threshold) vs Flight-level (top-X per flight)
// From ML team email: Customer-level is simpler and aligns with business objective
type RankingMode = 'customer-level' | 'flight-level';

interface FlightRankingConfig {
  topXPerFlight: number;  // Number of top customers to target per flight
  // Simulated ranking for demo purposes
  customerRankOnFlight: number;  // This customer's rank on the flight (1 = highest)
  totalCustomersOnFlight: number;  // Total customers eligible on this flight
}

interface AgentPhase {
  phase: 'idle' | 'loading' | 'planner' | 'worker' | 'solver' | 'complete';
  step?: number;
}

interface EvaluationResult {
  type: string;
  status: 'pending' | 'running' | 'complete';
  result?: string;
  recommendation?: string;
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

// Demo scenarios - now with flight ranking info for flight-level mode
const SCENARIOS: { [key: string]: { customer: CustomerData; flight: FlightData; ml: MLScores; pricing: PricingData; flightRanking: FlightRankingConfig } } = {
  'ABC123': {
    customer: {
      name: 'Sarah Johnson',
      loyaltyTier: 'G',
      tierDisplay: 'Gold',
      annualRevenue: 4200,
      acceptanceRate: 0.33,
      tenureDays: 1095,
      lastContactedDays: 14,  // Last contacted 14 days ago
      isDistressed: false,
    },
    flight: {
      flightNumber: 'AA2847',
      route: 'DFW → LAX',
      departureDate: 'Jan 15, 2026',
      hoursToDepart: 96,
      currentCabin: 'Economy',
      availableSeats: { 'Business': 12, 'Premium': 8, 'MCE': 14 },
      estimatedLDF: 72,  // 72% expected load factor
      needsProactiveTreatment: true,  // Has inventory to fill
    },
    ml: {
      businessProb: 0.72,
      businessConf: 0.88,
      premiumProb: 0.65,
      premiumConf: 0.91,
      mceProb: 0.82,
      mceConf: 0.95,
    },
    pricing: {
      businessBase: 499,
      premiumBase: 249,
      mceBase: 89,
    },
    flightRanking: {
      topXPerFlight: 10,
      customerRankOnFlight: 3,  // Sarah is #3 on this flight
      totalCustomersOnFlight: 45,
    },
  },
  'LMN456': {
    customer: {
      name: 'Emily Chen',
      loyaltyTier: 'E',
      tierDisplay: 'Executive Platinum',
      annualRevenue: 118000,
      acceptanceRate: 0.58,
      tenureDays: 3650,
      recentIssue: { type: 'seat_assignment_change', date: 'Jan 10' },
      lastContactedDays: 30,  // Last contacted 30 days ago
      isDistressed: false,
    },
    flight: {
      flightNumber: 'AA100',
      route: 'LAX → LHR',
      departureDate: 'Jan 16, 2026',
      hoursToDepart: 120,
      currentCabin: 'Premium Economy',
      availableSeats: { 'Business': 16, 'Premium': 8, 'MCE': 14 },
      estimatedLDF: 65,  // 65% - international flight with inventory
      needsProactiveTreatment: true,
    },
    ml: {
      businessProb: 0.85,
      businessConf: 0.95,
      premiumProb: 0.60,
      premiumConf: 0.88,
      mceProb: 0.45,
      mceConf: 0.92,
    },
    pricing: {
      businessBase: 770,
      premiumBase: 399,
      mceBase: 89,
    },
    flightRanking: {
      topXPerFlight: 10,
      customerRankOnFlight: 1,  // Emily is #1 on this flight (VIP, high score)
      totalCustomersOnFlight: 120,
    },
  },
  'JKL789': {
    customer: {
      name: 'David Kim',
      loyaltyTier: 'G',
      tierDisplay: 'Gold',
      annualRevenue: 1800,
      acceptanceRate: 0.125,
      tenureDays: 730,
      lastContactedDays: 3,  // Recently contacted - may suppress
      isDistressed: false,
    },
    flight: {
      flightNumber: 'AA2847',
      route: 'DFW → LAX',
      departureDate: 'Jan 15, 2026',
      hoursToDepart: 84,
      currentCabin: 'Economy',
      availableSeats: { 'Business': 12, 'Premium': 8, 'MCE': 14 },
      estimatedLDF: 88,  // High load factor - less need for proactive
      needsProactiveTreatment: false,
    },
    ml: {
      businessProb: 0.25,
      businessConf: 0.75,
      premiumProb: 0.35,
      premiumConf: 0.82,
      mceProb: 0.55,
      mceConf: 0.90,
    },
    pricing: {
      businessBase: 499,
      premiumBase: 249,
      mceBase: 89,
    },
    flightRanking: {
      topXPerFlight: 10,
      customerRankOnFlight: 15,  // David is #15 - below top 10 cutoff
      totalCustomersOnFlight: 45,
    },
  },
  // New scenario: Distressed customer (should be suppressed)
  'XYZ999': {
    customer: {
      name: 'Michael Torres',
      loyaltyTier: 'P',
      tierDisplay: 'Platinum',
      annualRevenue: 28000,
      acceptanceRate: 0.45,
      tenureDays: 1825,
      lastContactedDays: 0,  // Currently being contacted about disruption
      isDistressed: true,    // Flight was cancelled, rebooking in progress
    },
    flight: {
      flightNumber: 'AA445',
      route: 'ORD → MIA',
      departureDate: 'Jan 15, 2026',
      hoursToDepart: 48,
      currentCabin: 'Economy',
      availableSeats: { 'Business': 4, 'Premium': 2, 'MCE': 8 },
      estimatedLDF: 92,  // High load factor
      needsProactiveTreatment: false,
    },
    ml: {
      businessProb: 0.68,
      businessConf: 0.85,
      premiumProb: 0.55,
      premiumConf: 0.88,
      mceProb: 0.72,
      mceConf: 0.91,
    },
    pricing: {
      businessBase: 399,
      premiumBase: 199,
      mceBase: 69,
    },
    flightRanking: {
      topXPerFlight: 10,
      customerRankOnFlight: 5,  // Michael would be #5 if not distressed
      totalCustomersOnFlight: 38,
    },
  },
};

// Tier colors
const TIER_COLORS: { [key: string]: string } = {
  'G': 'text-yellow-400',
  'P': 'text-purple-400',
  'E': 'text-slate-300',
  'K': 'text-amber-300',
};

const TIER_BG: { [key: string]: string } = {
  'G': 'bg-yellow-900/30 border-yellow-500/50',
  'P': 'bg-purple-900/30 border-purple-500/50',
  'E': 'bg-slate-700/50 border-slate-400/50',
  'K': 'bg-amber-900/30 border-amber-500/50',
};

// PLANNER PROMPT - Decides what to check
const PLANNER_PROMPT_TEMPLATE = `I am the Planner. My job is to look at the customer data and make a plan of what things to check.

## What I have:
- Customer information (name, loyalty tier, revenue, recent issues)
- Flight information (departure time, load factor)
- ML scores (propensity and confidence for each offer)

## Suppression Checks (Check These First):
1. **Distressed Customer**: Is customer experiencing travel disruption? → If yes, SUPPRESS
2. **Recently Contacted**: Was customer contacted within {minDaysSinceContact} days? → If yes, SUPPRESS
3. **Flight Timing**: Is departure within {sendoutTiming} hours? → If not, queue for later
4. **Flight LDF**: Is flight LDF < {minLDFForProactive}%? → If not, lower priority

## If Not Suppressed, I Plan to Check:
- **CONFIDENCE**: Is ML confidence < {minConfidence}%? → Need to evaluate confidence trade-off
- **RELATIONSHIP**: Does customer have recent service issue? → Need to consider goodwill
- **PRICE_SENSITIVITY**: Does customer have low acceptance rate? → May need discount
- **VIP_TREATMENT**: Is annual revenue >= ${"{vipRevenueThreshold}"}? → VIP handling
- **EXPECTED_VALUE**: Which offer has highest EV?

## My Task:
Look at the data and create a list of things the Worker should check. Only include checks that are relevant based on the data I see.`;

// WORKER RULES - Deterministic rules for each check type
const WORKER_RULES_TEMPLATE = `I am the Worker. The Planner gave me a list of things to check. For each one, I call tools via MCP to get data, then apply these rules:

## CONFIDENCE Check:
- Call: get_ml_scores via MCP
- If best EV offer has confidence < {minConfidence}% AND there's a safer offer with confidence > 85%
- Recommend: Switch to safer offer

## RELATIONSHIP Check:
- Call: get_service_history via MCP
- If customer has recent service issue AND annual revenue >= ${"{vipRevenueThreshold}"}
- Recommend: Apply {goodwillDiscountPercent}% goodwill discount (pre-approved policy)

## PRICE_SENSITIVITY Check:
- Call: get_customer_behavior via MCP
- If acceptance rate < 30%
- Recommend: Apply up to {maxDiscount}% discount to improve conversion

## VIP_TREATMENT Check:
- Call: get_customer_value via MCP
- If annual revenue >= ${"{vipRevenueThreshold}"}
- Recommend: Priority handling with best available offer

## EXPECTED_VALUE Check:
- Call: get_pricing_catalog via MCP
- Calculate: EV = probability × price × margin for each offer
- Recommend: Offer with highest EV

## My Task:
Go through each check from the Planner, call the needed tools, and write down what I found.`;

// SOLVER PROMPT - Makes final decision
const SOLVER_PROMPT_TEMPLATE = `I am the Solver. The Worker did all the checks and gave me the results. Now I need to make the final decision.

## What I Have:
- All the check results from the Worker
- ML scores and confidence levels
- Customer information
- Available offers with prices

## Decision Rules:
1. **Start with Best EV**: Begin with the offer that has highest expected value
2. **Apply CONFIDENCE result**: If Worker said "switch to safer", pick the high-confidence offer
3. **Apply RELATIONSHIP result**: If Worker said "apply goodwill", add {goodwillDiscountPercent}% discount
4. **Apply PRICE_SENSITIVITY result**: If Worker said "apply discount", add up to {maxDiscount}% discount
5. **Check Score Threshold**: Only send if ML score >= {scoreThreshold}%
6. **Cap Discounts**: Never exceed max discount limits per offer type

## Final Steps:
1. Make my decision (which offer, what price)
2. Call LLM to craft personalized message for the customer
3. Give the offer + message to the Channel for delivery

## My Task:
Look at all the Worker's findings, apply the rules above, make a final decision, craft a message, and hand it to the Channel.`;

export default function BusinessAgentDemo() {
  const [selectedPNR, setSelectedPNR] = useState<string>('ABC123');
  const [agentPhase, setAgentPhase] = useState<AgentPhase>({ phase: 'idle' });
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [plannerThought, setPlannerThought] = useState<string>('');
  const [solverThought, setSolverThought] = useState<string>('');
  const [finalDecision, setFinalDecision] = useState<FinalDecision | null>(null);
  const [showingDecision, setShowingDecision] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<number>(0);
  const [showPrompt, setShowPrompt] = useState(false);
  const [hitlEnabled, setHitlEnabled] = useState(false);
  const [hitlPending, setHitlPending] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<FinalDecision | null>(null);

  // Editable prompt state - now split into 3 prompts
  const [editedPlannerPrompt, setEditedPlannerPrompt] = useState<string | null>(null);
  const [editedWorkerPrompt, setEditedWorkerPrompt] = useState<string | null>(null);
  const [editedSolverPrompt, setEditedSolverPrompt] = useState<string | null>(null);
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [activePromptTab, setActivePromptTab] = useState<'planner' | 'worker' | 'solver'>('planner');
  const [promptVersion, setPromptVersion] = useState(1);

  // Adjustable decision variables - these represent POLICY CONFIG (JSON-based)
  const [variables, setVariables] = useState<DecisionVariables>({
    minConfidence: 60,
    maxDiscount: 15,
    minExpectedValue: 100,
    vipRevenueThreshold: 50000,
    goodwillDiscountPercent: 10,
    // New: Sendout timing (from PDF: 72/48/24 hrs)
    sendoutTiming: 72,
    // New: Suppression rules
    minDaysSinceContact: 7,  // Don't contact if contacted within 7 days
    suppressDistressed: true,
    // New: Flight LDF threshold
    minLDFForProactive: 85,  // Only proactively offer if LDF below 85%
  });

  // Score threshold for sending offers (from meeting: "If score > 0.7, send")
  const [scoreThreshold, setScoreThreshold] = useState<number>(70);

  // Generate current prompts with variables replaced
  const currentPlannerPrompt = (editedPlannerPrompt || PLANNER_PROMPT_TEMPLATE)
    .replace('{minDaysSinceContact}', variables.minDaysSinceContact.toString())
    .replace('{sendoutTiming}', variables.sendoutTiming.toString())
    .replace('{minLDFForProactive}', variables.minLDFForProactive.toString())
    .replace('{minConfidence}', variables.minConfidence.toString())
    .replace('{vipRevenueThreshold}', variables.vipRevenueThreshold.toLocaleString());

  const currentWorkerPrompt = (editedWorkerPrompt || WORKER_RULES_TEMPLATE)
    .replace(/{minConfidence}/g, variables.minConfidence.toString())
    .replace(/{vipRevenueThreshold}/g, variables.vipRevenueThreshold.toLocaleString())
    .replace(/{goodwillDiscountPercent}/g, variables.goodwillDiscountPercent.toString())
    .replace(/{maxDiscount}/g, variables.maxDiscount.toString());

  const currentSolverPrompt = (editedSolverPrompt || SOLVER_PROMPT_TEMPLATE)
    .replace('{goodwillDiscountPercent}', variables.goodwillDiscountPercent.toString())
    .replace('{maxDiscount}', variables.maxDiscount.toString())
    .replace('{scoreThreshold}', scoreThreshold.toString());

  // Ranking Mode: Customer-level (threshold) vs Flight-level (top-X)
  // From ML team email: Customer-level is simpler, aligns with business objective
  const [rankingMode, setRankingMode] = useState<RankingMode>('customer-level');
  const [topXPerFlight, setTopXPerFlight] = useState<number>(10);

  const scenario = SCENARIOS[selectedPNR];

  // Reset when PNR changes
  useEffect(() => {
    setAgentPhase({ phase: 'idle' });
    setEvaluations([]);
    setPlannerThought('');
    setSolverThought('');
    setFinalDecision(null);
    setShowingDecision(false);
    setPipelineStep(0);
    setHitlPending(false);
    setPendingDecision(null);
  }, [selectedPNR]);

  // Run the agent simulation
  const runAgent = useCallback(async () => {
    setAgentPhase({ phase: 'loading' });
    setEvaluations([]);
    setPlannerThought('');
    setSolverThought('');
    setFinalDecision(null);
    setShowingDecision(false);
    setPipelineStep(0);
    setHitlPending(false);
    setPendingDecision(null);

    await sleep(300);

    // Pipeline animation: Eligible Flights → PNRs → Passengers → ML Score → Policy → Decision
    for (let i = 1; i <= 6; i++) {
      setPipelineStep(i);
      await sleep(400);
    }

    await sleep(300);

    // Phase 1: Planner
    setAgentPhase({ phase: 'planner' });

    // Build planner thought based on data
    const thoughts: string[] = [];
    const evalSteps: EvaluationResult[] = [];

    // Show which prompt is being used
    const hasCustomPrompts = editedPlannerPrompt || editedWorkerPrompt || editedSolverPrompt;
    if (hasCustomPrompts) {
      thoughts.push(`📝 I'm using YOUR custom instructions (version ${promptVersion})`);
      const customParts = [];
      if (editedPlannerPrompt) customParts.push('Planner');
      if (editedWorkerPrompt) customParts.push('Worker');
      if (editedSolverPrompt) customParts.push('Solver');
      thoughts.push(`   → Modified: ${customParts.join(', ')}\n`);
    } else {
      thoughts.push(`📝 I'm using my standard 3-prompt setup (Planner + Worker + Solver)\n`);
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    // First: Check SUPPRESSION RULES (from PDF)
    thoughts.push(`🛡️ First, let me check if I should even send an offer...`);
    await sleep(600);
    setPlannerThought(thoughts.join('\n'));

    // Check if customer is distressed
    const isDistressed = scenario.customer.isDistressed && variables.suppressDistressed;
    if (isDistressed) {
      thoughts.push(`❌ NO OFFER: This customer is having travel problems right now`);
      setPlannerThought(thoughts.join('\n'));
      await sleep(800);
      setFinalDecision({
        offerType: 'SUPPRESSED',
        offerName: 'No Offer (Customer Having Problems)',
        price: 0,
        discount: 0,
        expectedValue: 0,
        confidence: 'N/A',
        channel: 'N/A',
        reasoning: "Not a good time to send marketing - they're dealing with travel disruption",
      });
      setAgentPhase({ phase: 'complete' });
      setShowingDecision(true);
      return;
    }
    thoughts.push(`✓ They're not having any problems`);
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    // Check recently contacted
    const recentlyContacted = scenario.customer.lastContactedDays < variables.minDaysSinceContact;
    if (recentlyContacted) {
      thoughts.push(`❌ NO OFFER: We just contacted them ${scenario.customer.lastContactedDays} days ago (need to wait ${variables.minDaysSinceContact} days)`);
      setPlannerThought(thoughts.join('\n'));
      await sleep(800);
      setFinalDecision({
        offerType: 'SUPPRESSED',
        offerName: 'No Offer (Too Soon)',
        price: 0,
        discount: 0,
        expectedValue: 0,
        confidence: 'N/A',
        channel: 'N/A',
        reasoning: `We contacted them ${scenario.customer.lastContactedDays} days ago - need to wait ${variables.minDaysSinceContact - scenario.customer.lastContactedDays} more days so they don't get annoyed`,
      });
      setAgentPhase({ phase: 'complete' });
      setShowingDecision(true);
      return;
    }
    thoughts.push(`✓ Last contact was ${scenario.customer.lastContactedDays} days ago (that's fine)`);
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    // Check sendout timing
    const withinSendoutWindow = scenario.flight.hoursToDepart <= variables.sendoutTiming;
    if (!withinSendoutWindow) {
      thoughts.push(`⏳ Note: Flight is in ${scenario.flight.hoursToDepart} hours (I send at ${variables.sendoutTiming} hours before)`);
      thoughts.push(`   → I'll save this for later`);
    } else {
      thoughts.push(`✓ Flight is in ${scenario.flight.hoursToDepart} hours - that's the right time to send`);
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    // Check flight LDF (proactive treatment eligibility)
    const needsProactive = scenario.flight.estimatedLDF < variables.minLDFForProactive;
    if (!needsProactive && !scenario.flight.needsProactiveTreatment) {
      thoughts.push(`📊 This flight is ${scenario.flight.estimatedLDF}% full (it's filling up well)`);
      thoughts.push(`   → Lower priority - the flight doesn't need much help`);
    } else {
      thoughts.push(`✓ This flight is ${scenario.flight.estimatedLDF}% full - we need to fill more seats!`);
    }
    await sleep(600);
    setPlannerThought(thoughts.join('\n'));

    thoughts.push(`\n✅ All checks passed - okay to send an offer!`);
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    // Show data fetching via MCP
    thoughts.push(`\n🔍 Now I need to get ${scenario.customer.name}'s detailed information...`);
    await sleep(500);
    setPlannerThought(thoughts.join('\n'));

    thoughts.push(`📞 Calling tool: get_customer_service_history via MCP`);
    await sleep(600);
    setPlannerThought(thoughts.join('\n'));

    // Analyze what needs evaluation
    const hasLowConfidence = scenario.ml.businessConf < (variables.minConfidence / 100);
    const hasRecentIssue = !!scenario.customer.recentIssue;
    const isVIP = scenario.customer.annualRevenue >= variables.vipRevenueThreshold;
    const isPriceSensitive = scenario.customer.acceptanceRate < 0.3;

    thoughts.push(`✓ Got the data back!`);
    if (hasRecentIssue) {
      thoughts.push(`   Found: Recent service issue - "${scenario.customer.recentIssue?.type}"`);
    }
    thoughts.push(`   Annual revenue: $${scenario.customer.annualRevenue.toLocaleString()}`);
    thoughts.push(`   Acceptance rate: ${(scenario.customer.acceptanceRate * 100).toFixed(0)}%`);
    await sleep(700);
    setPlannerThought(thoughts.join('\n'));

    if (hasLowConfidence) {
      thoughts.push(`⚠️ The computer is only ${(scenario.ml.businessConf * 100).toFixed(0)}% sure about Business Class (minimum is ${variables.minConfidence}%)`);
      evalSteps.push({ type: 'CONFIDENCE', status: 'pending', result: 'I need to check: Is the computer sure enough about this offer?' });
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    if (hasRecentIssue) {
      thoughts.push(`⚠️ Found a problem in their history: "${scenario.customer.recentIssue?.type}" on ${scenario.customer.recentIssue?.date}`);
      thoughts.push(`   (This came from the service history tool)`);
      evalSteps.push({ type: 'RELATIONSHIP', status: 'pending', result: 'I need to check: Should I give them something to make them feel better?' });
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    if (isPriceSensitive) {
      thoughts.push(`💰 This customer usually only accepts ${(scenario.customer.acceptanceRate * 100).toFixed(0)}% of offers - they might need a discount`);
      evalSteps.push({ type: 'PRICE_SENSITIVITY', status: 'pending', result: 'I need to check: Will they only buy if I give them a discount?' });
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    if (isVIP) {
      thoughts.push(`⭐ This is a VIP customer - they spend $${scenario.customer.annualRevenue.toLocaleString()} per year!`);
      evalSteps.push({ type: 'VIP_TREATMENT', status: 'pending', result: 'I need to check: Should I give them special treatment?' });
    }
    await sleep(400);
    setPlannerThought(thoughts.join('\n'));

    if (evalSteps.length === 0) {
      thoughts.push(`✅ This looks straightforward - nothing special to worry about`);
      evalSteps.push({ type: 'EXPECTED_VALUE', status: 'pending', result: 'I just need to pick the offer that will make the most money' });
    }

    thoughts.push(`\n📋 My plan is ready! I have ${evalSteps.length} thing(s) to check`);
    setPlannerThought(thoughts.join('\n'));
    setEvaluations(evalSteps);

    await sleep(800);

    // Phase 2: Worker - Execute evaluations
    setAgentPhase({ phase: 'worker', step: 0 });

    for (let i = 0; i < evalSteps.length; i++) {
      setAgentPhase({ phase: 'worker', step: i });

      // Update current eval to running
      setEvaluations(prev => prev.map((e, idx) =>
        idx === i ? { ...e, status: 'running', result: 'Calling tools to get the data I need...' } : e
      ));

      await sleep(600);

      // Show tool invocation for each evaluation type
      let toolCall = '';
      if (evalSteps[i].type === 'CONFIDENCE') {
        toolCall = '📞 Calling: get_ml_scores via MCP → Got confidence levels for all offers';
      } else if (evalSteps[i].type === 'RELATIONSHIP') {
        toolCall = '📞 Calling: get_service_history via MCP → Found recent issue details';
      } else if (evalSteps[i].type === 'PRICE_SENSITIVITY') {
        toolCall = '📞 Calling: get_customer_behavior via MCP → Got purchase history';
      } else if (evalSteps[i].type === 'VIP_TREATMENT') {
        toolCall = '📞 Calling: get_customer_value via MCP → Got lifetime revenue data';
      } else {
        toolCall = '📞 Calling: get_pricing_catalog via MCP → Got current prices';
      }

      setEvaluations(prev => prev.map((e, idx) =>
        idx === i ? { ...e, result: toolCall } : e
      ));

      await sleep(600);

      // Calculate result based on eval type
      let recommendation = '';
      if (evalSteps[i].type === 'CONFIDENCE') {
        recommendation = `Maybe give them a cheaper, safer offer instead since the computer isn't very sure`;
      } else if (evalSteps[i].type === 'RELATIONSHIP') {
        recommendation = `Give them ${variables.goodwillDiscountPercent}% off to make them feel better about the problem (Already approved by management)`;
      } else if (evalSteps[i].type === 'PRICE_SENSITIVITY') {
        recommendation = `Give them ${variables.maxDiscount}% off so they're more likely to buy`;
      } else if (evalSteps[i].type === 'VIP_TREATMENT') {
        recommendation = `Give them the best offer with extra care - they're important!`;
      } else {
        recommendation = `Just pick whichever offer will make the most money`;
      }

      // Update eval to complete
      setEvaluations(prev => prev.map((e, idx) =>
        idx === i ? { ...e, status: 'complete', recommendation } : e
      ));

      await sleep(500);
    }

    await sleep(800);

    // Phase 3: Solver
    setAgentPhase({ phase: 'solver' });

    // Calculate final decision
    const businessEV = scenario.ml.businessProb * scenario.pricing.businessBase;
    // Premium EV available for future use: scenario.ml.premiumProb * scenario.pricing.premiumBase
    const mceEV = scenario.ml.mceProb * scenario.pricing.mceBase;

    let selectedOffer = 'Business';
    let selectedPrice = scenario.pricing.businessBase;
    let selectedEV = businessEV;
    let discount = 0;
    let confidence = 'HIGH';

    // Apply solver logic based on evaluations
    const solverThoughts: string[] = [];

    // Show ranking mode being used
    const mlScorePercent = scenario.ml.businessProb * 100;

    if (rankingMode === 'customer-level') {
      // CUSTOMER-LEVEL RANKING: Simple threshold-based decision
      const passesThreshold = mlScorePercent >= scoreThreshold;

      solverThoughts.push(`📊 Checking Score: The computer says ${mlScorePercent.toFixed(0)}%`);
      solverThoughts.push(`   My rule is: Only send if score is ${scoreThreshold}% or higher`);
      await sleep(500);
      setSolverThought(solverThoughts.join('\n'));

      if (!passesThreshold) {
        solverThoughts.push(`\n❌ ${mlScorePercent.toFixed(0)}% is too low → Not sending`);
        setSolverThought(solverThoughts.join('\n'));
        await sleep(800);
        setFinalDecision({
          offerType: 'SUPPRESSED',
          offerName: 'No Offer (Score Too Low)',
          price: 0,
          discount: 0,
          expectedValue: 0,
          confidence: 'N/A',
          channel: 'N/A',
          reasoning: `The computer's score was ${mlScorePercent.toFixed(0)}% but I need at least ${scoreThreshold}%`,
        });
        setAgentPhase({ phase: 'complete' });
        await sleep(300);
        setShowingDecision(true);
        return;
      }

      solverThoughts.push(`✅ Score is high enough → Moving forward`);
    } else {
      // FLIGHT-LEVEL RANKING: Top-X per flight
      const { customerRankOnFlight, totalCustomersOnFlight } = scenario.flightRanking;
      const passesRanking = customerRankOnFlight <= topXPerFlight;

      solverThoughts.push(`📊 Checking Ranking: Looking at everyone on flight ${scenario.flight.flightNumber}`);
      solverThoughts.push(`   There are ${totalCustomersOnFlight} people total, and this customer is #${customerRankOnFlight}`);
      solverThoughts.push(`   My rule is: Only send to the top ${topXPerFlight} people on each flight`);
      await sleep(500);
      setSolverThought(solverThoughts.join('\n'));

      if (!passesRanking) {
        solverThoughts.push(`\n❌ They're #${customerRankOnFlight}, which is outside my top ${topXPerFlight} → Not sending an offer`);
        setSolverThought(solverThoughts.join('\n'));
        await sleep(800);
        setFinalDecision({
          offerType: 'SUPPRESSED',
          offerName: 'No Offer (Not in Top Group)',
          price: 0,
          discount: 0,
          expectedValue: 0,
          confidence: 'N/A',
          channel: 'N/A',
          reasoning: `This customer is #${customerRankOnFlight} on the flight - only sending to top ${topXPerFlight}`,
        });
        setAgentPhase({ phase: 'complete' });
        await sleep(300);
        setShowingDecision(true);
        return;
      }

      solverThoughts.push(`✅ They're #${customerRankOnFlight}, which is in my top ${topXPerFlight} → Moving forward`);
    }
    solverThoughts.push(`\n📜 Now looking at what I found in my checks...`);
    await sleep(600);
    setSolverThought(solverThoughts.join('\n'));

    // Check if we need to apply discounts or change offer
    if (hasLowConfidence && scenario.ml.businessConf < 0.7) {
      // Switch to safer offer
      if (mceEV > 50) {
        selectedOffer = 'MCE';
        selectedPrice = scenario.pricing.mceBase;
        selectedEV = mceEV;
        confidence = 'HIGH';
        solverThoughts.push(`→ I'm going to give them MCE instead (the computer is ${(scenario.ml.mceConf * 100).toFixed(0)}% sure about that one)`);
      }
    } else if (hasRecentIssue && isVIP) {
      // Apply goodwill discount
      discount = variables.goodwillDiscountPercent;
      selectedPrice = scenario.pricing.businessBase * (1 - discount / 100);
      selectedEV = scenario.ml.businessProb * selectedPrice;
      solverThoughts.push(`→ I'm giving them ${discount}% off because they're important and had a problem`);
    } else if (isPriceSensitive) {
      // Apply price sensitivity discount
      discount = variables.maxDiscount;
      selectedPrice = scenario.pricing.businessBase * (1 - discount / 100);
      selectedEV = scenario.ml.businessProb * selectedPrice * 1.5; // Assume higher conversion
      solverThoughts.push(`→ I'm giving them ${discount}% off because they usually only buy when there's a discount`);
    } else {
      solverThoughts.push(`→ Everything looks good - going with Business Class at the regular price`);
    }

    await sleep(800);
    setSolverThought(solverThoughts.join('\n'));

    solverThoughts.push(`\n✅ My final decision: ${selectedOffer} for $${selectedPrice.toFixed(0)}`);
    setSolverThought(solverThoughts.join('\n'));

    await sleep(800);

    // LLM Message Crafting Step
    solverThoughts.push(`\n💬 Now let me write a nice personalized message...`);
    solverThoughts.push(`📞 Calling LLM: generate_personalized_message`);
    setSolverThought(solverThoughts.join('\n'));

    await sleep(1200);

    // Generate personalized message based on context
    let personalizedMessage = '';
    if (hasRecentIssue && isVIP) {
      personalizedMessage = `Hi ${scenario.customer.name.split(' ')[0]}, we noticed you experienced a ${scenario.customer.recentIssue?.type} recently. As a valued ${scenario.customer.tierDisplay} member, we'd like to offer you a complimentary upgrade to ${selectedOffer} for just $${selectedPrice.toFixed(0)} (${discount}% off) on your upcoming flight. We appreciate your loyalty!`;
    } else if (selectedOffer === 'Business') {
      personalizedMessage = `${scenario.customer.name.split(' ')[0]}, experience the luxury of Business Class on your ${scenario.flight.route} flight for just $${selectedPrice.toFixed(0)}. Enjoy priority boarding, premium dining, and lie-flat seats!`;
    } else if (selectedOffer === 'MCE') {
      personalizedMessage = `Hi ${scenario.customer.name.split(' ')[0]}! Stretch out with Main Cabin Extra on ${scenario.flight.flightNumber}. Get more legroom and priority boarding for only $${selectedPrice.toFixed(0)}.`;
    } else {
      personalizedMessage = `${scenario.customer.name.split(' ')[0]}, upgrade your travel experience on flight ${scenario.flight.flightNumber} for just $${selectedPrice.toFixed(0)}!`;
    }

    solverThoughts.push(`✓ LLM generated personalized message:`);
    solverThoughts.push(`   "${personalizedMessage}"`);
    solverThoughts.push(`\n📤 Now giving this to the Channel so they can send it!`);
    setSolverThought(solverThoughts.join('\n'));

    await sleep(1000);

    // Build final decision
    const decision: FinalDecision = {
      offerType: selectedOffer,
      offerName: selectedOffer === 'Business' ? 'Business Class Upgrade' :
                 selectedOffer === 'Premium' ? 'Premium Economy Upgrade' : 'Main Cabin Extra',
      price: selectedPrice,
      discount,
      expectedValue: selectedEV,
      confidence,
      channel: scenario.customer.loyaltyTier === 'E' ? 'Email' : 'Push',
      reasoning: solverThoughts.join(' '),
    };

    // If HITL enabled, pause for human approval
    if (hitlEnabled) {
      solverThoughts.push(`\n⏸️ HITL Enabled: Awaiting human approval before sending offer...`);
      setSolverThought(solverThoughts.join('\n'));
      setPendingDecision(decision);
      setHitlPending(true);
      setAgentPhase({ phase: 'complete' });
      return; // Don't auto-approve
    }

    // Auto-approve if HITL disabled
    setFinalDecision(decision);
    setAgentPhase({ phase: 'complete' });
    await sleep(300);
    setShowingDecision(true);

  }, [selectedPNR, scenario, variables, scoreThreshold, hitlEnabled, editedPlannerPrompt, editedWorkerPrompt, editedSolverPrompt, promptVersion, rankingMode, topXPerFlight]);

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
              Watch how I figure out which upgrade offer to give each customer
            </p>
            <p className="text-slate-500 text-sm mt-1">
              Step 1: Make a plan → Step 2: Do the checks (calling tools via MCP) → Step 3: Make the decision → Give to Channel for sending
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Show Prompt Button */}
            <button
              onClick={() => setShowPrompt(!showPrompt)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                showPrompt
                  ? 'bg-purple-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <span>📝</span>
              {showPrompt ? 'Hide Prompt' : 'View Prompt'}
            </button>

            {/* HITL Toggle */}
            <div className="flex items-center gap-2 bg-slate-700 rounded-lg px-3 py-2">
              <span className="text-sm text-slate-300">HITL</span>
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

            <select
              value={selectedPNR}
              onChange={(e) => setSelectedPNR(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white"
            >
              <option value="ABC123">ABC123 - Sarah (Gold, Easy)</option>
              <option value="LMN456">LMN456 - Emily (Exec Plat, Issue)</option>
              <option value="JKL789">JKL789 - David (Recently Contacted)</option>
              <option value="XYZ999">XYZ999 - Michael (Distressed)</option>
            </select>

            <button
              onClick={runAgent}
              disabled={(agentPhase.phase !== 'idle' && agentPhase.phase !== 'complete') || hitlPending}
              className={`px-6 py-2 rounded-lg font-medium transition-all ${
                (agentPhase.phase === 'idle' || agentPhase.phase === 'complete') && !hitlPending
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  : 'bg-slate-600 text-slate-400 cursor-not-allowed'
              }`}
            >
              {agentPhase.phase === 'idle' ? '▶ Run Agent' :
               agentPhase.phase === 'complete' && !hitlPending ? '↻ Run Again' : '⏳ Running...'}
            </button>
          </div>
        </div>

        {/* Prompt Display/Edit Panel */}
        {showPrompt && (
          <>
            {/* Prompt Behavior Examples */}
            <div className="bg-gradient-to-r from-purple-900/30 to-cyan-900/30 border border-purple-500/30 rounded-xl p-5 mb-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">💡</span>
                <span className="font-semibold text-purple-300">How Prompt Changes Affect Behavior</span>
              </div>
              <div className="text-sm text-slate-300 space-y-2">
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-medium text-cyan-300 mb-1">Example 1: Change VIP Threshold</div>
                  <div className="text-xs text-slate-400">
                    Change "annual revenue {'>'}= $50,000" to "$100,000"
                    <br />
                    <span className="text-emerald-300">→ Result:</span> Fewer customers get VIP treatment, agent becomes more selective
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-medium text-cyan-300 mb-1">Example 2: Add Urgency Rule</div>
                  <div className="text-xs text-slate-400">
                    Add "If flight departs in {'<'} 24 hours, increase discount by 5%"
                    <br />
                    <span className="text-emerald-300">→ Result:</span> Agent gives bigger discounts for last-minute flights
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-medium text-cyan-300 mb-1">Example 3: Change Confidence Threshold</div>
                  <div className="text-xs text-slate-400">
                    Change "If ML confidence {'<'} 60%" to "{'<'} 80%"
                    <br />
                    <span className="text-emerald-300">→ Result:</span> Agent becomes more cautious, switches to safer offers more often
                  </div>
                </div>
              </div>
              <div className="mt-3 text-xs text-purple-200 bg-purple-900/30 p-2 rounded">
                <strong>Try it:</strong> Edit the prompt below and click "Run Agent" to see how the agent's decisions change!
              </div>
            </div>

            {/* Determine if any prompts are customized */}
            <div className={`bg-slate-800/80 border rounded-xl p-5 mb-6 ${
              isEditingPrompt ? 'border-cyan-500' : (editedPlannerPrompt || editedWorkerPrompt || editedSolverPrompt) ? 'border-emerald-500' : 'border-purple-500/50'
            }`}>
                  {/* Tab Buttons */}
                  <div className="flex gap-2 mb-4 border-b border-slate-700 pb-2">
                    <button
                      onClick={() => setActivePromptTab('planner')}
                      className={`px-4 py-2 text-sm rounded-t-lg transition-all ${
                        activePromptTab === 'planner'
                          ? 'bg-purple-600/30 text-purple-300 border-b-2 border-purple-500'
                          : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
                      }`}
                    >
                      <span className="mr-1">📋</span> Planner
                      {editedPlannerPrompt && <span className="ml-1 text-[10px]">●</span>}
                    </button>
                    <button
                      onClick={() => setActivePromptTab('worker')}
                      className={`px-4 py-2 text-sm rounded-t-lg transition-all ${
                        activePromptTab === 'worker'
                          ? 'bg-cyan-600/30 text-cyan-300 border-b-2 border-cyan-500'
                          : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
                      }`}
                    >
                      <span className="mr-1">🔍</span> Worker
                      {editedWorkerPrompt && <span className="ml-1 text-[10px]">●</span>}
                    </button>
                    <button
                      onClick={() => setActivePromptTab('solver')}
                      className={`px-4 py-2 text-sm rounded-t-lg transition-all ${
                        activePromptTab === 'solver'
                          ? 'bg-emerald-600/30 text-emerald-300 border-b-2 border-emerald-500'
                          : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
                      }`}
                    >
                      <span className="mr-1">✅</span> Solver
                      {editedSolverPrompt && <span className="ml-1 text-[10px]">●</span>}
                    </button>
                  </div>

                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">📝</span>
                      <span className="font-semibold text-purple-300">
                        {activePromptTab === 'planner' && 'Planner Prompt'}
                        {activePromptTab === 'worker' && 'Worker Rules'}
                        {activePromptTab === 'solver' && 'Solver Prompt'}
                      </span>
                      <span className="text-xs text-slate-400">(Plain English Instructions)</span>
                      {(editedPlannerPrompt || editedWorkerPrompt || editedSolverPrompt) && (
                        <span className="text-xs bg-emerald-600 text-white px-2 py-0.5 rounded-full">
                          v{promptVersion} - Modified
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {!isEditingPrompt ? (
                        <button
                          onClick={() => {
                            setIsEditingPrompt(true);
                            // Initialize all prompts if not already edited
                            if (!editedPlannerPrompt) setEditedPlannerPrompt(currentPlannerPrompt);
                            if (!editedWorkerPrompt) setEditedWorkerPrompt(currentWorkerPrompt);
                            if (!editedSolverPrompt) setEditedSolverPrompt(currentSolverPrompt);
                          }}
                          className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg flex items-center gap-1 transition-all"
                        >
                          <span>✏️</span> Edit Prompt
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              // Parse all three prompts and extract values to update sliders
                              const allPrompts = [editedPlannerPrompt, editedWorkerPrompt, editedSolverPrompt].join('\n');

                              if (allPrompts) {
                                // Extract minDaysSinceContact - look for pattern like "within X days"
                                const daysMatch = allPrompts.match(/within\s+(\d+)\s+days?\s*→\s*SUPPRESS/i);
                                if (daysMatch) {
                                  const days = parseInt(daysMatch[1]);
                                  if (!isNaN(days) && days >= 1 && days <= 14) {
                                    setVariables(prev => ({ ...prev, minDaysSinceContact: days }));
                                  }
                                }

                                // Extract vipRevenueThreshold - look for pattern like ">= $XX,XXX"
                                const vipMatch = allPrompts.match(/revenue\s*>=?\s*\$(\d{1,3}(?:,?\d{3})*)/i);
                                if (vipMatch) {
                                  const amount = parseInt(vipMatch[1].replace(/,/g, ''));
                                  if (!isNaN(amount)) {
                                    setVariables(prev => ({ ...prev, vipRevenueThreshold: amount }));
                                  }
                                }

                                // Extract minConfidence - look for pattern like "< XX%"
                                const confMatch = allPrompts.match(/confidence\s*<\s*(\d+)%/i);
                                if (confMatch) {
                                  const conf = parseInt(confMatch[1]);
                                  if (!isNaN(conf) && conf >= 50 && conf <= 95) {
                                    setVariables(prev => ({ ...prev, minConfidence: conf }));
                                  }
                                }

                                // Extract goodwillDiscountPercent - look for pattern like "apply XX%"
                                const goodwillMatch = allPrompts.match(/apply\s+(\d+)%\s+goodwill/i);
                                if (goodwillMatch) {
                                  const disc = parseInt(goodwillMatch[1]);
                                  if (!isNaN(disc) && disc >= 0 && disc <= 20) {
                                    setVariables(prev => ({ ...prev, goodwillDiscountPercent: disc }));
                                  }
                                }

                                // Extract maxDiscount - look for pattern like "up to XX%"
                                const maxDiscMatch = allPrompts.match(/up to\s+(\d+)%\s+discount/i);
                                if (maxDiscMatch) {
                                  const disc = parseInt(maxDiscMatch[1]);
                                  if (!isNaN(disc) && disc >= 0 && disc <= 25) {
                                    setVariables(prev => ({ ...prev, maxDiscount: disc }));
                                  }
                                }

                                // Extract scoreThreshold - look for pattern like ">= XX%"
                                const scoreMatch = allPrompts.match(/score\s*>=?\s*(\d+)%/i);
                                if (scoreMatch) {
                                  const score = parseInt(scoreMatch[1]);
                                  if (!isNaN(score) && score >= 50 && score <= 95) {
                                    setScoreThreshold(score);
                                  }
                                }

                                // Extract sendoutTiming - look for pattern like "within XX hours"
                                const timingMatch = allPrompts.match(/within\s+(\d+)\s+hours/i);
                                if (timingMatch) {
                                  const hours = parseInt(timingMatch[1]);
                                  if (!isNaN(hours) && (hours === 24 || hours === 48 || hours === 72 || hours === 168)) {
                                    setVariables(prev => ({ ...prev, sendoutTiming: hours as 72 | 48 | 24 }));
                                  }
                                }

                                // Extract minLDFForProactive - look for pattern like "< XX%"
                                const ldfMatch = allPrompts.match(/LDF\s*<\s*(\d+)%/i);
                                if (ldfMatch) {
                                  const ldf = parseInt(ldfMatch[1]);
                                  if (!isNaN(ldf) && ldf >= 60 && ldf <= 95) {
                                    setVariables(prev => ({ ...prev, minLDFForProactive: ldf }));
                                  }
                                }
                              }

                              setIsEditingPrompt(false);
                              setPromptVersion(v => v + 1);
                            }}
                            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg flex items-center gap-1 transition-all"
                          >
                            <span>✓</span> Save Changes
                          </button>
                          <button
                            onClick={() => {
                              setIsEditingPrompt(false);
                              setEditedPlannerPrompt(null);
                              setEditedWorkerPrompt(null);
                              setEditedSolverPrompt(null);
                              setPromptVersion(1);
                            }}
                            className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 text-white text-xs rounded-lg flex items-center gap-1 transition-all"
                          >
                            <span>↺</span> Reset to Default
                          </button>
                        </>
                      )}
                    </div>
                  </div>

            {isEditingPrompt ? (
              <>
                {activePromptTab === 'planner' && (
                  <textarea
                    value={editedPlannerPrompt || currentPlannerPrompt}
                    onChange={(e) => setEditedPlannerPrompt(e.target.value)}
                    className="w-full h-80 text-sm text-slate-300 font-mono bg-slate-900/50 rounded-lg p-4 border border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
                    placeholder="Edit the planner prompt here..."
                  />
                )}
                {activePromptTab === 'worker' && (
                  <textarea
                    value={editedWorkerPrompt || currentWorkerPrompt}
                    onChange={(e) => setEditedWorkerPrompt(e.target.value)}
                    className="w-full h-80 text-sm text-slate-300 font-mono bg-slate-900/50 rounded-lg p-4 border border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 resize-none"
                    placeholder="Edit the worker rules here..."
                  />
                )}
                {activePromptTab === 'solver' && (
                  <textarea
                    value={editedSolverPrompt || currentSolverPrompt}
                    onChange={(e) => setEditedSolverPrompt(e.target.value)}
                    className="w-full h-80 text-sm text-slate-300 font-mono bg-slate-900/50 rounded-lg p-4 border border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                    placeholder="Edit the solver prompt here..."
                  />
                )}
              </>
            ) : (
              <>
                {activePromptTab === 'planner' && (
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-900/50 rounded-lg p-4 border border-slate-700 max-h-80 overflow-y-auto">
                    {editedPlannerPrompt || currentPlannerPrompt}
                  </pre>
                )}
                {activePromptTab === 'worker' && (
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-900/50 rounded-lg p-4 border border-slate-700 max-h-80 overflow-y-auto">
                    {editedWorkerPrompt || currentWorkerPrompt}
                  </pre>
                )}
                {activePromptTab === 'solver' && (
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-900/50 rounded-lg p-4 border border-slate-700 max-h-80 overflow-y-auto">
                    {editedSolverPrompt || currentSolverPrompt}
                  </pre>
                )}
              </>
            )}

            {isEditingPrompt ? (
              <div className="mt-3 p-3 bg-cyan-900/20 border border-cyan-500/30 rounded-lg text-xs text-cyan-200">
                <strong>✏️ Edit Mode:</strong> Modify the {activePromptTab} prompt above to change agent behavior. Try adding new rules, changing thresholds, or adjusting the decision logic.
                <div className="mt-2 pt-2 border-t border-cyan-500/30">
                  <strong>💡 Smart Parsing:</strong> When you save, I'll automatically detect changes to numbers and update the sliders below!
                  <ul className="mt-1 ml-4 space-y-0.5 text-[10px]">
                    <li>• Change "within 7 days" → Updates "Min Days Since Contact" slider</li>
                    <li>• Change "revenue {'>'}= $50,000" → Updates "VIP Revenue Threshold"</li>
                    <li>• Change "confidence {'<'} 60%" → Updates "Min Confidence" slider</li>
                    <li>• And more... Try it!</li>
                  </ul>
                </div>
              </div>
            ) : (editedPlannerPrompt || editedWorkerPrompt || editedSolverPrompt) ? (
              <div className="mt-3 p-3 bg-emerald-900/20 border border-emerald-500/30 rounded-lg text-xs text-emerald-200">
                <strong>✅ Custom Prompts Active (v{promptVersion}):</strong> You've modified the agent's instructions. Run the agent to see how your changes affect the decision! Click "Edit Prompt" to make more changes or "Reset to Default" to restore original.
              </div>
            ) : (
              <div className="mt-3 p-3 bg-amber-900/20 border border-amber-500/30 rounded-lg text-xs text-amber-200">
                <strong>💡 Key Insight:</strong> The agent's behavior is driven by plain English rules in 3 separate prompts (Planner, Worker, Solver). Click tabs to see each one, then "Edit Prompt" to modify, or change policy sliders to see how prompts update!
              </div>
            )}

            {/* Example Edits */}
            {isEditingPrompt && (
              <div className="mt-3 p-3 bg-slate-900/50 border border-slate-700 rounded-lg">
                <div className="text-xs text-slate-400 mb-2">💡 Try these edits for the {activePromptTab} prompt:</div>
                <div className="flex flex-wrap gap-2">
                  {activePromptTab === 'planner' && (
                    <>
                      <button
                        onClick={() => setEditedPlannerPrompt(prev => (prev || currentPlannerPrompt) + '\n\n## Additional Check:\n11. **Flight Timing**: Check departure time for urgency discounts')}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        + Add Timing Check
                      </button>
                      <button
                        onClick={() => setEditedPlannerPrompt(prev => (prev || currentPlannerPrompt).replace('SUPPRESS', 'DEFER (queue for later)'))}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        Change SUPPRESS → DEFER
                      </button>
                    </>
                  )}
                  {activePromptTab === 'worker' && (
                    <>
                      <button
                        onClick={() => setEditedWorkerPrompt(prev => (prev || currentWorkerPrompt) + '\n\n## AGGRESSIVE_PRICING Check:\n- If flight LDF < 50%, add extra 5% discount')}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        + Add Aggressive Pricing Rule
                      </button>
                      <button
                        onClick={() => setEditedWorkerPrompt(prev => (prev || currentWorkerPrompt).replace(/confidence\s*<\s*\d+%/, 'confidence < 80%'))}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        Raise Confidence Threshold to 80%
                      </button>
                    </>
                  )}
                  {activePromptTab === 'solver' && (
                    <>
                      <button
                        onClick={() => setEditedSolverPrompt(prev => (prev || currentSolverPrompt) + '\n\n## Premium Priority:\nAlways prefer Business Class for Executive Platinum members.')}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        + Add VIP Priority Rule
                      </button>
                      <button
                        onClick={() => setEditedSolverPrompt(prev => (prev || currentSolverPrompt).replace(/(\d+)%\s+goodwill/, '15% goodwill'))}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition-all"
                      >
                        Increase Goodwill to 15%
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
          </>
        )}

        {/* Decision Pipeline Flow - Shows the architecture from meeting notes */}
        <DecisionPipeline
          currentStep={pipelineStep}
          isRunning={agentPhase.phase !== 'idle' && agentPhase.phase !== 'complete'}
          scoreThreshold={scoreThreshold}
          mlScore={scenario.ml.businessProb}
          rankingMode={rankingMode}
          topXPerFlight={topXPerFlight}
          customerRank={scenario.flightRanking.customerRankOnFlight}
        />

        {/* Main Content Grid */}
        <div className="grid grid-cols-12 gap-6">

          {/* Left Column - Input Data */}
          <div className="col-span-4 space-y-4">
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="text-xl">📥</span> Input Data
              </h2>

              {/* Customer Card */}
              <div className={`rounded-xl p-4 mb-3 border ${TIER_BG[scenario.customer.loyaltyTier]}`}>
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-12 h-12 bg-slate-600 rounded-full flex items-center justify-center text-xl">
                    👤
                  </div>
                  <div>
                    <div className="font-semibold">{scenario.customer.name}</div>
                    <div className={`text-sm ${TIER_COLORS[scenario.customer.loyaltyTier]}`}>
                      {scenario.customer.tierDisplay} Member
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-slate-900/50 rounded-lg p-2">
                    <div className="text-slate-400 text-xs">Annual Revenue</div>
                    <div className="font-semibold">${scenario.customer.annualRevenue.toLocaleString()}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-lg p-2">
                    <div className="text-slate-400 text-xs">Accept Rate</div>
                    <div className="font-semibold">{(scenario.customer.acceptanceRate * 100).toFixed(0)}%</div>
                  </div>
                </div>
                {scenario.customer.recentIssue && (
                  <div className="mt-2 bg-red-900/30 border border-red-500/50 rounded-lg p-2 text-sm">
                    <span className="text-red-400">⚠️ Recent Issue:</span>{' '}
                    <span className="text-red-200">{scenario.customer.recentIssue.type}</span>
                  </div>
                )}
              </div>

              {/* Flight Card with LDF Indicator */}
              <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-4 mb-3">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="text-2xl">✈️</div>
                    <div>
                      <div className="font-semibold">{scenario.flight.flightNumber}</div>
                      <div className="text-blue-300">{scenario.flight.route}</div>
                    </div>
                  </div>
                  {/* Proactive Treatment Indicator */}
                  <div className={`text-[10px] px-2 py-0.5 rounded ${
                    scenario.flight.needsProactiveTreatment
                      ? 'bg-emerald-900/50 text-emerald-300'
                      : 'bg-slate-700 text-slate-400'
                  }`}>
                    {scenario.flight.needsProactiveTreatment ? '✓ Proactive OK' : '✗ High LDF'}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-slate-900/50 rounded-lg p-2">
                    <div className="text-slate-400 text-xs">Departure</div>
                    <div className="font-semibold">{scenario.flight.hoursToDepart}h away</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-lg p-2">
                    <div className="text-slate-400 text-xs">Current Cabin</div>
                    <div className="font-semibold">{scenario.flight.currentCabin}</div>
                  </div>
                </div>
                {/* LDF (Load Factor) Indicator */}
                <div className="mt-2 bg-slate-900/50 rounded-lg p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-400 text-xs">Est. Load Factor (LDF)</span>
                    <span className={`text-xs font-medium ${
                      scenario.flight.estimatedLDF < 70 ? 'text-emerald-400' :
                      scenario.flight.estimatedLDF < 85 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {scenario.flight.estimatedLDF}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full transition-all ${
                        scenario.flight.estimatedLDF < 70 ? 'bg-emerald-500' :
                        scenario.flight.estimatedLDF < 85 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${scenario.flight.estimatedLDF}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    {scenario.flight.estimatedLDF < 70
                      ? 'Low LDF → Good candidate for proactive offers'
                      : scenario.flight.estimatedLDF < 85
                        ? 'Medium LDF → May need offers'
                        : 'High LDF → Flight filling well, less urgency'}
                  </div>
                </div>
                <div className="mt-2 flex gap-2">
                  {Object.entries(scenario.flight.availableSeats).map(([cabin, seats]) => (
                    <div key={cabin} className="bg-slate-900/50 rounded px-2 py-1 text-xs">
                      <span className="text-slate-400">{cabin}:</span>{' '}
                      <span className="text-emerald-400">{seats} seats</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Suppression Status Card */}
              <div className={`rounded-xl p-3 mb-3 border ${
                scenario.customer.isDistressed || scenario.customer.lastContactedDays < variables.minDaysSinceContact
                  ? 'bg-red-900/20 border-red-500/30'
                  : 'bg-emerald-900/20 border-emerald-500/30'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🛡️</span>
                    <span className="text-sm font-medium">Suppression Check</span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    scenario.customer.isDistressed || scenario.customer.lastContactedDays < variables.minDaysSinceContact
                      ? 'bg-red-900/50 text-red-300'
                      : 'bg-emerald-900/50 text-emerald-300'
                  }`}>
                    {scenario.customer.isDistressed || scenario.customer.lastContactedDays < variables.minDaysSinceContact
                      ? '⚠️ May Suppress'
                      : '✓ Clear to Send'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                  <div className={`p-2 rounded ${
                    scenario.customer.isDistressed ? 'bg-red-900/30' : 'bg-slate-900/50'
                  }`}>
                    <div className="text-slate-400">Distressed</div>
                    <div className={scenario.customer.isDistressed ? 'text-red-300 font-medium' : 'text-emerald-300'}>
                      {scenario.customer.isDistressed ? '⚠️ Yes - Disrupted' : '✓ No'}
                    </div>
                  </div>
                  <div className={`p-2 rounded ${
                    scenario.customer.lastContactedDays < variables.minDaysSinceContact ? 'bg-red-900/30' : 'bg-slate-900/50'
                  }`}>
                    <div className="text-slate-400">Last Contact</div>
                    <div className={
                      scenario.customer.lastContactedDays < variables.minDaysSinceContact
                        ? 'text-red-300 font-medium'
                        : 'text-emerald-300'
                    }>
                      {scenario.customer.lastContactedDays}d ago
                      {scenario.customer.lastContactedDays < variables.minDaysSinceContact && ' (< min)'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Flight Ranking Card - Only shown in flight-level mode */}
              {rankingMode === 'flight-level' && (
                <div className="bg-purple-900/20 border border-purple-500/30 rounded-xl p-3 mb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">📊</span>
                      <span className="text-sm font-medium">Flight Ranking</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      scenario.flightRanking.customerRankOnFlight <= topXPerFlight
                        ? 'bg-emerald-900/50 text-emerald-300'
                        : 'bg-red-900/50 text-red-300'
                    }`}>
                      {scenario.flightRanking.customerRankOnFlight <= topXPerFlight
                        ? `In Top ${topXPerFlight}`
                        : `Outside Top ${topXPerFlight}`}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                    <div className="bg-slate-900/50 rounded p-2 text-center">
                      <div className="text-slate-400">Rank</div>
                      <div className={`text-lg font-bold ${
                        scenario.flightRanking.customerRankOnFlight <= topXPerFlight
                          ? 'text-emerald-400'
                          : 'text-red-400'
                      }`}>
                        #{scenario.flightRanking.customerRankOnFlight}
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-2 text-center">
                      <div className="text-slate-400">Total</div>
                      <div className="text-lg font-bold text-slate-300">
                        {scenario.flightRanking.totalCustomersOnFlight}
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-2 text-center">
                      <div className="text-slate-400">Cutoff</div>
                      <div className="text-lg font-bold text-purple-400">
                        Top {topXPerFlight}
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] text-purple-200 mt-2 bg-purple-900/30 p-2 rounded">
                    In Flight-Level mode, only the top {topXPerFlight} ranked customers on each flight receive offers
                  </div>
                </div>
              )}

              {/* ML Scores Card - Pure Intelligence from ML Service */}
              <div className="bg-purple-900/20 border border-purple-500/30 rounded-xl p-4 mb-3">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🤖</span>
                    <span className="font-semibold">ML Service</span>
                  </div>
                  <span className="text-[10px] text-purple-400 bg-purple-900/50 px-2 py-0.5 rounded">
                    Pure Intelligence
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2 -mt-1">
                  Raw propensity scores (blind to inventory/rules)
                </div>
                <div className="space-y-2">
                  {[
                    { name: 'Business', prob: scenario.ml.businessProb, conf: scenario.ml.businessConf },
                    { name: 'Premium', prob: scenario.ml.premiumProb, conf: scenario.ml.premiumConf },
                    { name: 'MCE', prob: scenario.ml.mceProb, conf: scenario.ml.mceConf },
                  ].map((item) => (
                    <div key={item.name} className="flex items-center gap-2">
                      <div className="w-16 text-xs text-slate-400">{item.name}</div>
                      <div className="flex-1 bg-slate-700 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-purple-500 h-full transition-all"
                          style={{ width: `${item.prob * 100}%` }}
                        />
                      </div>
                      <div className="w-12 text-xs text-right">
                        {(item.prob * 100).toFixed(0)}%
                      </div>
                      <div className={`w-16 text-xs text-right ${
                        item.conf >= 0.85 ? 'text-emerald-400' :
                        item.conf >= 0.7 ? 'text-amber-400' : 'text-red-400'
                      }`}>
                        ({(item.conf * 100).toFixed(0)}% conf)
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Pricing Card */}
              <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">💰</span>
                  <span className="font-semibold">Pricing</span>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1 bg-slate-900/50 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">Business</div>
                    <div className="font-bold text-amber-300">${scenario.pricing.businessBase}</div>
                  </div>
                  <div className="flex-1 bg-slate-900/50 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">Premium</div>
                    <div className="font-bold text-amber-300">${scenario.pricing.premiumBase}</div>
                  </div>
                  <div className="flex-1 bg-slate-900/50 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">MCE</div>
                    <div className="font-bold text-amber-300">${scenario.pricing.mceBase}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Middle Column - Agent Reasoning (Chain of Thought) */}
          <div className="col-span-5 space-y-4">
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-cyan-500/30 min-h-[500px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <span className="text-xl">🧠</span> What I'm Thinking
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-cyan-400 bg-cyan-900/50 px-2 py-1 rounded flex items-center gap-1">
                    <span className="animate-pulse">💭</span> Following My Steps
                  </span>
                </div>
              </div>
              <div className="text-[10px] text-slate-400 mb-4 -mt-2">
                I call tools via MCP to get customer data. Then I figure out what offer to give them. Then I hand it to the Channel.
              </div>

              {/* Phase Indicators */}
              <div className="flex items-center justify-between mb-6">
                {[
                  { id: 'planner', label: 'Step 1: Make a Plan', icon: '📋', desc: 'What should I check?' },
                  { id: 'worker', label: 'Step 2: Do the Checks', icon: '🔍', desc: 'Call tools via MCP' },
                  { id: 'solver', label: 'Step 3: Make Decision', icon: '✅', desc: 'Put it all together' },
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
                  <div className="bg-slate-900/50 rounded-xl p-4 border border-cyan-500/30">
                    <div className="text-xs text-cyan-400 mb-2 flex items-center gap-2">
                      <span>📋</span> STEP 1: MAKING MY PLAN
                    </div>
                    <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans">
                      {plannerThought}
                    </pre>
                  </div>
                )}

                {/* Worker Evaluations */}
                {['worker', 'solver', 'complete'].includes(agentPhase.phase) && evaluations.length > 0 && (
                  <div className="bg-slate-900/50 rounded-xl p-4 border border-purple-500/30">
                    <div className="text-xs text-purple-400 mb-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>⚙️</span> STEP 2: DOING MY CHECKS
                      </div>
                      <div className="text-[10px] text-purple-300 bg-purple-900/30 px-2 py-0.5 rounded">
                        Using MCP (Model Context Protocol) to call tools
                      </div>
                    </div>
                    <div className="space-y-2">
                      {evaluations.map((evaluation, idx) => (
                        <div
                          key={idx}
                          className={`flex items-center gap-3 p-2 rounded-lg transition-all ${
                            evaluation.status === 'running'
                              ? 'bg-purple-900/30 border border-purple-500/50'
                              : evaluation.status === 'complete'
                                ? 'bg-emerald-900/20 border border-emerald-500/30'
                                : 'bg-slate-800/50 border border-slate-600'
                          }`}
                        >
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                            evaluation.status === 'running'
                              ? 'bg-purple-600 animate-spin'
                              : evaluation.status === 'complete'
                                ? 'bg-emerald-600'
                                : 'bg-slate-600'
                          }`}>
                            {evaluation.status === 'complete' ? '✓' : evaluation.status === 'running' ? '◌' : idx + 1}
                          </div>
                          <div className="flex-1">
                            <div className="text-sm font-medium">{evaluation.type}</div>
                            {evaluation.result && evaluation.status === 'running' && (
                              <div className="text-xs text-purple-300 mt-1 italic">
                                {evaluation.result}
                              </div>
                            )}
                            {evaluation.result && evaluation.status === 'complete' && evaluation.result.includes('Calling:') && (
                              <div className="text-xs text-cyan-300 mt-1">
                                {evaluation.result}
                              </div>
                            )}
                            {evaluation.recommendation && (
                              <div className="text-xs text-emerald-300 mt-1">
                                → {evaluation.recommendation}
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
                  <div className="bg-slate-900/50 rounded-xl p-4 border border-emerald-500/30">
                    <div className="text-xs text-emerald-400 mb-2 flex items-center gap-2">
                      <span>✅</span> STEP 3: MAKING MY DECISION
                    </div>
                    <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans">
                      {solverThought}
                    </pre>
                  </div>
                )}

                {/* Idle State */}
                {agentPhase.phase === 'idle' && (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                    <div className="text-4xl mb-4">🎯</div>
                    <div className="text-lg">Click "Run Agent" to watch me work</div>
                    <div className="text-sm mt-2">You'll see me make a plan, call tools via MCP to get data, do my checks, decide, then give it to the Channel</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Decision & Variables */}
          <div className="col-span-3 space-y-4">
            {/* Final Decision */}
            <div className={`bg-slate-800/50 rounded-2xl p-5 border transition-all duration-500 ${
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
                  <span className="text-xs bg-amber-500 text-black px-2 py-0.5 rounded-full animate-pulse">
                    AWAITING APPROVAL
                  </span>
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
                      <div className={`text-lg font-bold ${
                        pendingDecision.confidence === 'HIGH' ? 'text-emerald-400' : 'text-amber-400'
                      }`}>
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
                      <span>✅</span> Approve & Send
                    </button>
                    <button
                      onClick={handleReject}
                      className="flex-1 bg-red-600 hover:bg-red-500 text-white font-medium py-3 rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                      <span>❌</span> Reject
                    </button>
                  </div>

                  <div className="text-xs text-amber-200 bg-amber-900/30 p-2 rounded text-center">
                    Human-in-the-Loop: Review agent recommendation before sending to customer
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
                      {finalDecision.offerType === 'REJECTED' ? 'REJECTED BY REVIEWER'
                        : finalDecision.offerType === 'SUPPRESSED' ? 'OFFER SUPPRESSED'
                        : hitlEnabled ? 'APPROVED & SENT' : 'RECOMMENDED OFFER'}
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
                        <div className="text-xs text-slate-400 mb-1">Channel (How to Send It)</div>
                        <div className="text-sm font-medium">{finalDecision.channel} Notification</div>
                        <div className="text-[10px] text-slate-400 mt-1">
                          The Channel decides the best way to send this offer based on customer preferences
                        </div>
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

            {/* Decision Variables - Representing Policy Config (JSON/GitHub) */}
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-amber-500/30">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <span className="text-xl">📜</span> Policy Config
                </h2>
                <span className="text-[10px] text-amber-400 bg-amber-900/50 px-2 py-0.5 rounded flex items-center gap-1">
                  <span>📁</span> JSON / GitHub
                </span>
              </div>
              <div className="text-[10px] text-slate-400 mb-2 -mt-2">
                Business rules externalized in config (no code deployment)
              </div>

              {agentPhase.phase !== 'idle' && (
                <div className="text-[10px] bg-cyan-900/30 border border-cyan-500/30 text-cyan-200 p-2 rounded mb-3">
                  💡 <strong>Tip:</strong> After changing any slider below, click "Run Agent" again to see the new behavior!
                </div>
              )}

              <div className="space-y-4">
                {/* Ranking Mode Toggle - from ML team email */}
                <div className="bg-cyan-900/20 border border-cyan-500/30 rounded-lg p-3 mb-2">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="text-sm text-slate-200 font-medium flex items-center gap-2">
                        <span>📊</span> Ranking Mode
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        How to select customers for offers
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <button
                      onClick={() => setRankingMode('customer-level')}
                      className={`p-2 rounded-lg text-xs font-medium transition-all border ${
                        rankingMode === 'customer-level'
                          ? 'bg-emerald-600 border-emerald-500 text-white'
                          : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500'
                      }`}
                    >
                      <div className="font-semibold">Customer-Level</div>
                      <div className="text-[10px] opacity-75 mt-0.5">P(buy) {'>'} threshold</div>
                    </button>
                    <button
                      onClick={() => setRankingMode('flight-level')}
                      className={`p-2 rounded-lg text-xs font-medium transition-all border ${
                        rankingMode === 'flight-level'
                          ? 'bg-purple-600 border-purple-500 text-white'
                          : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500'
                      }`}
                    >
                      <div className="font-semibold">Flight-Level</div>
                      <div className="text-[10px] opacity-75 mt-0.5">Top-X per flight</div>
                    </button>
                  </div>
                  <div className={`mt-2 p-2 rounded text-[10px] ${
                    rankingMode === 'customer-level'
                      ? 'bg-emerald-900/30 text-emerald-200'
                      : 'bg-purple-900/30 text-purple-200'
                  }`}>
                    {rankingMode === 'customer-level'
                      ? '✓ Recommended: Simpler, directly aligns with business objective (maximize purchases)'
                      : '⚠️ Complex: Requires ranking within each flight, may miss high-value customers'}
                  </div>
                </div>

                {/* Show Top X Per Flight slider when in flight-level mode */}
                {rankingMode === 'flight-level' && (
                  <div className="bg-purple-900/20 border border-purple-500/30 rounded-lg p-3">
                    <VariableSlider
                      label="Top X Per Flight"
                      value={topXPerFlight}
                      min={5}
                      max={25}
                      unit=""
                      onChange={setTopXPerFlight}
                      description="Send to top X ranked customers per flight"
                    />
                  </div>
                )}

                {/* Score Threshold - the key decision rule (only for customer-level) */}
                {rankingMode === 'customer-level' && (
                <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-3 mb-2">
                  <VariableSlider
                    label="Score Threshold"
                    value={scoreThreshold}
                    min={50}
                    max={90}
                    unit="%"
                    onChange={setScoreThreshold}
                    description="If ML score > threshold → SEND offer"
                  />
                </div>
                )}

                <VariableSlider
                  label="Min Confidence"
                  value={variables.minConfidence}
                  min={40}
                  max={90}
                  unit="%"
                  onChange={(v) => setVariables(prev => ({ ...prev, minConfidence: v }))}
                  description="Below this, agent prefers safer offer"
                />

                <VariableSlider
                  label="Max Discount"
                  value={variables.maxDiscount}
                  min={5}
                  max={25}
                  unit="%"
                  onChange={(v) => setVariables(prev => ({ ...prev, maxDiscount: v }))}
                  description="Maximum discount for price-sensitive"
                />

                <VariableSlider
                  label="VIP Threshold"
                  value={variables.vipRevenueThreshold / 1000}
                  min={20}
                  max={100}
                  unit="k"
                  prefix="$"
                  onChange={(v) => setVariables(prev => ({ ...prev, vipRevenueThreshold: v * 1000 }))}
                  description="Revenue to qualify as VIP"
                />

                <VariableSlider
                  label="Goodwill Discount"
                  value={variables.goodwillDiscountPercent}
                  min={5}
                  max={20}
                  unit="%"
                  onChange={(v) => setVariables(prev => ({ ...prev, goodwillDiscountPercent: v }))}
                  description="Discount for service recovery"
                />

                {/* Suppression Rules Section */}
                <div className="pt-3 mt-3 border-t border-slate-700">
                  <div className="text-xs text-red-400 font-medium mb-3 flex items-center gap-1">
                    <span>🛡️</span> Suppression Rules
                  </div>

                  {/* Sendout Timing */}
                  <div className="mb-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm text-slate-300">Sendout Timing</span>
                      <span className="text-sm font-mono text-cyan-400">{variables.sendoutTiming}h</span>
                    </div>
                    <div className="flex gap-2">
                      {([24, 48, 72] as const).map((hrs) => (
                        <button
                          key={hrs}
                          onClick={() => setVariables(prev => ({ ...prev, sendoutTiming: hrs }))}
                          className={`flex-1 py-1.5 rounded text-xs font-medium transition-all ${
                            variables.sendoutTiming === hrs
                              ? 'bg-cyan-600 text-white'
                              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                          }`}
                        >
                          {hrs}h
                        </button>
                      ))}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">Hours before departure to send offers</div>
                  </div>

                  <VariableSlider
                    label="Min Days Since Contact"
                    value={variables.minDaysSinceContact}
                    min={1}
                    max={14}
                    unit="d"
                    onChange={(v) => setVariables(prev => ({ ...prev, minDaysSinceContact: v }))}
                    description="Suppress if contacted within X days"
                  />

                  <VariableSlider
                    label="Max LDF for Proactive"
                    value={variables.minLDFForProactive}
                    min={60}
                    max={95}
                    unit="%"
                    onChange={(v) => setVariables(prev => ({ ...prev, minLDFForProactive: v }))}
                    description="Only offer if flight LDF below this %"
                  />

                  {/* Suppress Distressed Toggle */}
                  <div className="flex items-center justify-between mt-3 p-2 bg-slate-900/50 rounded-lg">
                    <div>
                      <div className="text-sm text-slate-300">Suppress Distressed</div>
                      <div className="text-[10px] text-slate-500">Don't send to disrupted travelers</div>
                    </div>
                    <button
                      onClick={() => setVariables(prev => ({ ...prev, suppressDistressed: !prev.suppressDistressed }))}
                      className={`relative w-10 h-5 rounded-full transition-all ${
                        variables.suppressDistressed ? 'bg-red-500' : 'bg-slate-600'
                      }`}
                    >
                      <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all ${
                        variables.suppressDistressed ? 'left-5' : 'left-0.5'
                      }`} />
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-4 p-3 bg-amber-900/20 border border-amber-500/30 rounded-lg text-xs text-amber-200">
                <strong>💡 Config Agility:</strong> Change policies without code deployment! Adjust thresholds and re-run to see impact.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper Components
function VariableSlider({
  label,
  value,
  min,
  max,
  unit,
  prefix = '',
  onChange,
  description,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  prefix?: string;
  onChange: (value: number) => void;
  description: string;
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm text-slate-300">{label}</span>
        <span className="text-sm font-mono text-cyan-400">
          {prefix}{value}{unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
      <div className="text-[10px] text-slate-500 mt-1">{description}</div>
    </div>
  );
}

// Decision Pipeline Component - Shows the architecture flow from meeting notes
function DecisionPipeline({
  currentStep,
  isRunning,
  scoreThreshold,
  mlScore,
  rankingMode,
  topXPerFlight,
  customerRank,
}: {
  currentStep: number;
  isRunning: boolean;
  scoreThreshold: number;
  mlScore: number;
  rankingMode: RankingMode;
  topXPerFlight: number;
  customerRank: number;
}) {
  const steps = [
    { id: 1, icon: '✈️', label: 'Eligible Flights', desc: 'Flights with inventory' },
    { id: 2, icon: '📋', label: 'PNRs', desc: 'Reservation records' },
    { id: 3, icon: '👥', label: 'Passengers', desc: 'Individual travelers' },
    { id: 4, icon: '🤖', label: 'ML Score', desc: 'Propensity prediction', highlight: true },
    { id: 5, icon: '📜', label: 'Policy', desc: 'Business rules', highlight: true },
    { id: 6, icon: '🎯', label: 'Decision', desc: 'Send or suppress' },
  ];

  // Determine if customer passes based on ranking mode
  const passesThreshold = rankingMode === 'customer-level'
    ? mlScore * 100 >= scoreThreshold
    : customerRank <= topXPerFlight;

  return (
    <div className="bg-slate-800/30 rounded-xl p-4 mb-6 border border-slate-700">
      {/* Architecture Label */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Offer Agent Decision Pipeline</span>
          <span className={`text-xs px-2 py-0.5 rounded ${
            rankingMode === 'customer-level'
              ? 'bg-emerald-900/50 text-emerald-300'
              : 'bg-purple-900/50 text-purple-300'
          }`}>
            {rankingMode === 'customer-level' ? 'Customer-Level Ranking' : 'Flight-Level Ranking'}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-purple-500"></div>
            <span className="text-slate-400">ML Service (Pure Intelligence)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-amber-500"></div>
            <span className="text-slate-400">Policy Application (Rules)</span>
          </div>
        </div>
      </div>

      {/* Pipeline Steps */}
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

              {/* Show threshold comparison on ML Score step */}
              {step.id === 4 && currentStep >= 4 && (
                <div className="mt-2 px-2 py-1 bg-purple-900/50 rounded text-xs">
                  Score: <span className="text-purple-300 font-mono">{(mlScore * 100).toFixed(0)}%</span>
                </div>
              )}

              {/* Show ranking rule on Policy step */}
              {step.id === 5 && currentStep >= 5 && (
                <div className="mt-2 px-2 py-1 bg-amber-900/50 rounded text-xs">
                  {rankingMode === 'customer-level' ? (
                    <>Threshold: <span className="text-amber-300 font-mono">{scoreThreshold}%</span></>
                  ) : (
                    <>Top-X: <span className="text-amber-300 font-mono">#{customerRank}</span> / {topXPerFlight}</>
                  )}
                </div>
              )}

              {/* Show decision on final step */}
              {step.id === 6 && currentStep >= 6 && (
                <div className={`mt-2 px-2 py-1 rounded text-xs font-medium ${
                  passesThreshold ? 'bg-emerald-900/50 text-emerald-300' : 'bg-red-900/50 text-red-300'
                }`}>
                  {rankingMode === 'customer-level' ? (
                    passesThreshold
                      ? `${(mlScore * 100).toFixed(0)}% ≥ ${scoreThreshold}% → SEND`
                      : `${(mlScore * 100).toFixed(0)}% < ${scoreThreshold}% → SUPPRESS`
                  ) : (
                    passesThreshold
                      ? `#${customerRank} ≤ Top ${topXPerFlight} → SEND`
                      : `#${customerRank} > Top ${topXPerFlight} → SUPPRESS`
                  )}
                </div>
              )}
            </div>

            {/* Connector Arrow */}
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

      {/* Explanation Text */}
      {currentStep === 0 && (
        <div className="mt-4 text-center text-sm text-slate-400">
          Click "Run Agent" to see the decision pipeline in action
        </div>
      )}
    </div>
  );
}

// Utility
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
