import type { PNRSummary } from '../types';

interface Props {
  pnrList: PNRSummary[];
  selectedPNR: string | null;
  onSelect: (pnr: string) => void;
  onRun: () => void;
  isRunning: boolean;
}

const tierColors: Record<string, string> = {
  'Gold': 'bg-yellow-100 text-yellow-800 border-yellow-300',
  'Platinum': 'bg-gray-100 text-gray-800 border-gray-300',
  'Platinum Pro': 'bg-gray-200 text-gray-900 border-gray-400',
  'Executive Platinum': 'bg-purple-100 text-purple-800 border-purple-300',
  'General': 'bg-slate-100 text-slate-600 border-slate-300',
};

const scenarioColors: Record<string, string> = {
  'Easy Choice': 'bg-green-100 text-green-700',
  'Confidence Trade-off': 'bg-amber-100 text-amber-700',
  'Relationship Trade-off': 'bg-blue-100 text-blue-700',
  'Guardrail: Inventory': 'bg-red-100 text-red-700',
  'Guardrail: Customer': 'bg-red-100 text-red-700',
  'Price Trade-off': 'bg-purple-100 text-purple-700',
};

// What each scenario demonstrates about agent capabilities
// Shows: (1) Data source via MCP, (2) Guardrail check, (3) Agent trade-off decision
const scenarioDescriptions: Record<string, { demonstrates: string; expectedOutcome: string; keyInsight: string }> = {
  'ABC123': {
    demonstrates: '✅ EASY CHOICE (Baseline)',
    expectedOutcome: 'Business @ $199',
    keyInsight: 'ML MCP → 85% confidence, Business EV ($143) >> MCE EV ($35). No trade-off needed.',
  },
  'XYZ789': {
    demonstrates: '🤔 TRADE-OFF: Confidence vs Opportunity',
    expectedOutcome: 'Agent decides: Business or MCE?',
    keyInsight: 'ML MCP returns LOW confidence (50%) for Business EV ($165) vs HIGH confidence (92%) for MCE EV ($52). Trust uncertain prediction or play safe?',
  },
  'LMN456': {
    demonstrates: '🤔 TRADE-OFF: Revenue vs Relationship',
    expectedOutcome: 'Agent decides: Push $770 or nurture?',
    keyInsight: 'Customer MCP shows recent service recovery. Agent weighs: $770 Business offer vs gentler MCE to protect $118K lifetime value.',
  },
  'DEF321': {
    demonstrates: '🚫 GUARDRAIL: Inventory Constraint',
    expectedOutcome: 'NO OFFER (blocked)',
    keyInsight: 'Flight MCP returns 0 available seats → Guardrail blocks before agent runs. Agent cannot override system constraints.',
  },
  'GHI654': {
    demonstrates: '🚫 GUARDRAIL: Customer Protection',
    expectedOutcome: 'NO OFFER (blocked)',
    keyInsight: 'Customer MCP returns suppression flag (recent complaint) → Guardrail blocks. Agent works WITHIN protective rules.',
  },
  'JKL789': {
    demonstrates: '🤔 TRADE-OFF: Price Elasticity',
    expectedOutcome: 'Agent decides discount level',
    keyInsight: 'ML MCP shows: 18% P(buy) @ $199 vs 52% @ $159. Agent weighs conversion gain vs margin erosion.',
  },
};

export function PNRSelector({ pnrList, selectedPNR, onSelect, onRun, isRunning }: Props) {
  const selected = pnrList.find(p => p.pnr === selectedPNR);
  const scenarioInfo = selectedPNR ? scenarioDescriptions[selectedPNR] : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Scenario
          </label>
          <select
            value={selectedPNR || ''}
            onChange={(e) => onSelect(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                     bg-white cursor-pointer"
            disabled={isRunning}
          >
            <option value="">Choose a PNR...</option>
            {pnrList.map((pnr) => (
              <option key={pnr.pnr} value={pnr.pnr}>
                {pnr.pnr} - {pnr.customer_name} ({pnr.customer_tier}) - {pnr.route}
              </option>
            ))}
          </select>
        </div>

        {selected && (
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-medium border ${tierColors[selected.customer_tier] || tierColors['General']}`}>
              {selected.customer_tier}
            </span>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${scenarioColors[selected.scenario_tag] || 'bg-gray-100 text-gray-700'}`}>
              {selected.scenario_tag}
            </span>
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700">
              T-{selected.hours_to_departure}hrs
            </span>
          </div>
        )}

        <button
          onClick={onRun}
          disabled={!selectedPNR || isRunning}
          className={`px-6 py-2.5 rounded-lg font-semibold text-white transition-all
            ${!selectedPNR || isRunning
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 shadow-md hover:shadow-lg'
            }`}
        >
          {isRunning ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Evaluating...
            </span>
          ) : (
            'Run Evaluation'
          )}
        </button>
      </div>

      {/* Scenario Description - What this demonstrates */}
      {scenarioInfo && (
        <div className="mt-4 bg-slate-50 rounded-lg p-4 border border-slate-200">
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                🎯 This Scenario Demonstrates
              </div>
              <div className="text-sm font-medium text-slate-700">
                {scenarioInfo.demonstrates}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                📋 Expected Outcome
              </div>
              <div className="text-sm font-medium text-slate-700">
                {scenarioInfo.expectedOutcome}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                💡 Key Insight (Agent Reasoning)
              </div>
              <div className="text-sm font-medium text-slate-700">
                {scenarioInfo.keyInsight}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
