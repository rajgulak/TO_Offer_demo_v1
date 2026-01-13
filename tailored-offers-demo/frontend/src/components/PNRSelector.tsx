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
  'Standard': 'bg-green-100 text-green-700',
  'Follow-up': 'bg-blue-100 text-blue-700',
  'International': 'bg-indigo-100 text-indigo-700',
  'Cold Start': 'bg-orange-100 text-orange-700',
  'Suppressed': 'bg-red-100 text-red-700',
};

// What each scenario demonstrates about agent capabilities (in plain English!)
const scenarioDescriptions: Record<string, { demonstrates: string; expectedOutcome: string; keyInsight: string }> = {
  'ABC123': {
    demonstrates: 'A typical customer who should get an upgrade offer',
    expectedOutcome: '✅ Offer Business Class for $171 via app notification',
    keyInsight: 'Agent did the math: 40% chance × $171 = $68 avg revenue beats 60% chance × $89 = $53 for cheaper MCE',
  },
  'XYZ789': {
    demonstrates: 'Customer who looked at our offer before but didn\'t buy',
    expectedOutcome: '✅ Offer Business Class for $165 (discounted!)',
    keyInsight: 'Agents noticed they opened our last offer but didn\'t buy → try a lower price this time',
  },
  'LMN456': {
    demonstrates: 'Our most valuable customer - needs VIP treatment',
    expectedOutcome: '✅ Offer Business Class for $770 via email',
    keyInsight: 'Executive Platinum members get a premium message tone and their preferred contact method',
  },
  'DEF321': {
    demonstrates: 'New customer + no seats available - what happens?',
    expectedOutcome: '❌ NO OFFER sent',
    keyInsight: 'Agents checked inventory and found Business is SOLD OUT - saved us from an embarrassing mistake!',
  },
  'GHI654': {
    demonstrates: 'Customer who recently complained - should we contact them?',
    expectedOutcome: '❌ NO OFFER sent',
    keyInsight: 'Agents found this customer complained 5 days ago - contacting them now would make things WORSE',
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
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${scenarioColors[selected.scenario_tag] || scenarioColors['Standard']}`}>
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
