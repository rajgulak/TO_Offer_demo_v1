import { useState } from 'react';

export function ArchitectureOverview() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl shadow-lg text-white overflow-hidden">
      {/* Collapsed Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-4">
          <span className="text-2xl">🏗️</span>
          <div className="text-left">
            <h2 className="font-semibold">MVP1 Architecture: LangGraph + LLM Reasoning + Existing Systems</h2>
            <p className="text-sm text-slate-300">
              Hybrid architecture: Rules-based workflow + LLM reasoning agents — no system changes required
            </p>
          </div>
        </div>
        <span className={`text-xl transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-6 pb-6 space-y-6">
          {/* Architecture Diagram */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-center text-sm text-slate-400 mb-4">Hybrid Architecture Stack</div>
            <div className="flex flex-col items-center gap-3 text-sm">
              {/* Orchestration Layer */}
              <div className="flex items-center gap-2 w-full justify-center">
                <div className="bg-violet-600 px-4 py-2 rounded-lg text-center flex-1 max-w-xs">
                  <div className="font-bold">LangGraph</div>
                  <div className="text-xs opacity-80">Workflow Orchestration</div>
                </div>
                <div className="bg-orange-600 px-4 py-2 rounded-lg text-center flex-1 max-w-xs">
                  <div className="font-bold">Temporal</div>
                  <div className="text-xs opacity-80">Durable Execution (Future)</div>
                </div>
              </div>

              <span className="text-xl">↓</span>

              {/* Agent Layer */}
              <div className="flex items-center gap-2 w-full justify-center flex-wrap">
                <div className="bg-slate-600 px-3 py-2 rounded-lg text-center">
                  <div className="font-bold">Rules Agents</div>
                  <div className="text-xs opacity-80">Fast, Deterministic</div>
                </div>
                <div className="bg-blue-600 px-3 py-2 rounded-lg text-center">
                  <div className="font-bold">LLM Agents</div>
                  <div className="text-xs opacity-80">Reasoning, GenAI</div>
                </div>
              </div>

              <span className="text-xl">↓</span>

              {/* Tool Layer */}
              <div className="bg-purple-600 px-4 py-2 rounded-lg text-center w-full max-w-md">
                <div className="font-bold">MCP Tools</div>
                <div className="text-xs opacity-80">Standard Interface to Existing Systems</div>
              </div>

              <span className="text-xl">↓</span>

              {/* Data Layer */}
              <div className="bg-emerald-600 px-4 py-2 rounded-lg text-center w-full max-w-md">
                <div className="font-bold">Existing Systems (Unchanged)</div>
                <div className="text-xs opacity-80">AADV DB, ML Models, DCSID, RM Engine</div>
              </div>
            </div>
          </div>

          {/* Agent Types - Rules vs LLM */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🤖 Agent Types in This Demo</h3>
            <div className="grid md:grid-cols-2 gap-4">
              {/* Rules-Based Agents */}
              <div className="bg-slate-900/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">⚡</span>
                  <span className="font-semibold text-slate-300">Rules-Based Agents</span>
                  <span className="text-xs bg-slate-600 px-2 py-0.5 rounded">Fast</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-400">
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                    <span><strong>Customer Intelligence</strong> - Eligibility checks</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                    <span><strong>Flight Optimization</strong> - Inventory analysis</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                    <span><strong>Channel & Timing</strong> - Delivery rules</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                    <span><strong>Measurement</strong> - A/B assignment</span>
                  </li>
                </ul>
                <div className="mt-3 text-xs text-slate-500">
                  Deterministic, low-latency, no API calls needed
                </div>
              </div>

              {/* LLM-Powered Agents */}
              <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">🧠</span>
                  <span className="font-semibold text-blue-300">LLM-Powered Agents</span>
                  <span className="text-xs bg-blue-600 px-2 py-0.5 rounded">AI</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-300">
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-blue-400 rounded-full"></span>
                    <span><strong>Offer Orchestration</strong> - Strategic reasoning</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-blue-400 rounded-full"></span>
                    <span><strong>Personalization</strong> - GenAI messaging</span>
                  </li>
                </ul>
                <div className="mt-3 text-xs text-blue-400">
                  Dynamic reasoning, considers nuances rules miss
                </div>
                <div className="mt-2 text-xs bg-blue-900/50 p-2 rounded">
                  Supports: OpenAI GPT-4, Anthropic Claude
                </div>
              </div>
            </div>
          </div>

          {/* Why Hybrid? */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🎯 Why Hybrid Architecture?</h3>
            <div className="grid md:grid-cols-3 gap-3">
              <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                <div className="text-2xl mb-2">⚡</div>
                <div className="text-sm font-medium">Performance</div>
                <div className="text-xs text-slate-400">Rules for speed-critical paths</div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                <div className="text-2xl mb-2">🧠</div>
                <div className="text-sm font-medium">Intelligence</div>
                <div className="text-xs text-slate-400">LLM for complex decisions</div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                <div className="text-2xl mb-2">💰</div>
                <div className="text-sm font-medium">Cost Efficient</div>
                <div className="text-xs text-slate-400">LLM only where it adds value</div>
              </div>
            </div>
          </div>

          {/* State-Based Choreography */}
          <div className="bg-violet-900/30 border border-violet-500/30 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-violet-300 mb-3">🔄 State-Based Choreography (NOT Central Orchestration)</h3>

            {/* Key Concept */}
            <div className="bg-slate-900/50 rounded-lg p-3 mb-4">
              <div className="text-xs text-slate-400 mb-2">How agents work together:</div>
              <div className="text-sm text-slate-200 mb-3">
                There is <span className="text-red-400 font-bold">NO "Boss" Agent</span> telling others what to do.
                Instead, agents pass a <span className="text-violet-400 font-bold">Shared State Object</span> like a baton in a relay race.
              </div>

              {/* Visual: The Baton Passing */}
              <div className="flex items-center justify-center gap-1 text-xs py-2 overflow-x-auto">
                <div className="bg-violet-600 px-2 py-1 rounded whitespace-nowrap">📦 State</div>
                <span className="text-violet-400">→</span>
                <div className="bg-slate-700 px-2 py-1 rounded whitespace-nowrap">Agent 1</div>
                <span className="text-violet-400">→</span>
                <div className="bg-violet-600 px-2 py-1 rounded whitespace-nowrap">📦 State</div>
                <span className="text-violet-400">→</span>
                <div className="bg-slate-700 px-2 py-1 rounded whitespace-nowrap">Agent 2</div>
                <span className="text-violet-400">→</span>
                <div className="bg-violet-600 px-2 py-1 rounded whitespace-nowrap">📦 State</div>
                <span className="text-violet-400">→</span>
                <div className="bg-slate-700 px-2 py-1 rounded whitespace-nowrap">...</div>
              </div>
            </div>

            {/* Why This Matters */}
            <div className="grid md:grid-cols-2 gap-4 text-sm mb-4">
              <div className="bg-red-900/30 rounded-lg p-3">
                <div className="font-medium text-red-300 mb-2">❌ Central Orchestration (We DON'T do this)</div>
                <ul className="text-slate-300 space-y-1 text-xs">
                  <li>• One "supervisor" agent calls all shots</li>
                  <li>• Requires huge, complex prompts</li>
                  <li>• Single point of failure</li>
                  <li>• Hard to debug and maintain</li>
                </ul>
              </div>
              <div className="bg-emerald-900/30 rounded-lg p-3">
                <div className="font-medium text-emerald-300 mb-2">✅ State-Based Choreography (We DO this)</div>
                <ul className="text-slate-300 space-y-1 text-xs">
                  <li>• Each agent has ONE focused job</li>
                  <li>• Short, accurate prompts</li>
                  <li>• Agents are independent & testable</li>
                  <li>• Easy to add/modify agents</li>
                </ul>
              </div>
            </div>

            {/* Tech Stack */}
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <div className="font-medium text-violet-300 mb-2">LangGraph (Active)</div>
                <ul className="text-slate-300 space-y-1 text-xs">
                  <li>• Defines the agent sequence</li>
                  <li>• Manages the shared State Object</li>
                  <li>• Handles conditional routing (if/then)</li>
                  <li>• Streams results as each agent completes</li>
                </ul>
              </div>
              <div>
                <div className="font-medium text-orange-300 mb-2">Temporal (Future)</div>
                <ul className="text-slate-300 space-y-1 text-xs">
                  <li>• Durable execution guarantees</li>
                  <li>• Retry policies for API calls</li>
                  <li>• Long-running workflow support</li>
                  <li>• Production-grade reliability</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Feedback Loop Pattern - Business Focused */}
          <div className="bg-amber-900/30 border border-amber-500/30 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-amber-300 mb-3">🔄 Feedback Loops → Business Outcomes</h3>

            {/* Business Problem First */}
            <div className="bg-slate-900/50 rounded-lg p-3 mb-4">
              <div className="text-xs text-slate-400 mb-2">Why do we need feedback loops?</div>
              <div className="text-sm text-slate-200">
                Without learning, we leave <span className="text-amber-400 font-semibold">$2-5M annually</span> on the table from:
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                <div className="bg-red-900/30 p-2 rounded text-center">
                  <div className="text-red-400 font-bold">Wrong Offers</div>
                  <div className="text-slate-400">Low conversion</div>
                </div>
                <div className="bg-red-900/30 p-2 rounded text-center">
                  <div className="text-red-400 font-bold">Bad Timing</div>
                  <div className="text-slate-400">Customer ignores</div>
                </div>
                <div className="bg-red-900/30 p-2 rounded text-center">
                  <div className="text-red-400 font-bold">Over-contact</div>
                  <div className="text-slate-400">Brand damage</div>
                </div>
              </div>
            </div>

            {/* Learning Loops with Business Metrics */}
            <div className="space-y-3">
              {/* Loop 1: Offer Selection */}
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">💰</span>
                    <span className="text-sm font-medium text-amber-300">Offer Selection Learning</span>
                  </div>
                  <span className="text-xs bg-emerald-600 px-2 py-0.5 rounded">+12% Revenue</span>
                </div>
                <div className="text-xs text-slate-300 grid md:grid-cols-2 gap-2">
                  <div>
                    <div className="text-slate-400 mb-1">What we track:</div>
                    <ul className="space-y-0.5">
                      <li>• Business vs MCE acceptance by segment</li>
                      <li>• Price elasticity by customer tier</li>
                    </ul>
                  </div>
                  <div>
                    <div className="text-slate-400 mb-1">How it improves:</div>
                    <ul className="space-y-0.5">
                      <li>• Offer Orchestration learns optimal EV calc</li>
                      <li>• Discount strategy refined per segment</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Loop 2: Personalization */}
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">✨</span>
                    <span className="text-sm font-medium text-amber-300">Personalization Learning</span>
                  </div>
                  <span className="text-xs bg-emerald-600 px-2 py-0.5 rounded">+8% CTR</span>
                </div>
                <div className="text-xs text-slate-300 grid md:grid-cols-2 gap-2">
                  <div>
                    <div className="text-slate-400 mb-1">What we track:</div>
                    <ul className="space-y-0.5">
                      <li>• Message open rates by tone</li>
                      <li>• Click-through by benefit highlighted</li>
                    </ul>
                  </div>
                  <div>
                    <div className="text-slate-400 mb-1">How it improves:</div>
                    <ul className="space-y-0.5">
                      <li>• LLM prompt tuned with winning patterns</li>
                      <li>• A/B test winning copy becomes context</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Loop 3: Suppression */}
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🛡️</span>
                    <span className="text-sm font-medium text-amber-300">Suppression Learning</span>
                  </div>
                  <span className="text-xs bg-emerald-600 px-2 py-0.5 rounded">-40% Complaints</span>
                </div>
                <div className="text-xs text-slate-300 grid md:grid-cols-2 gap-2">
                  <div>
                    <div className="text-slate-400 mb-1">What we track:</div>
                    <ul className="space-y-0.5">
                      <li>• Unsubscribe rates post-offer</li>
                      <li>• Complaint patterns by contact frequency</li>
                    </ul>
                  </div>
                  <div>
                    <div className="text-slate-400 mb-1">How it improves:</div>
                    <ul className="space-y-0.5">
                      <li>• Customer Intel learns fatigue signals</li>
                      <li>• Auto-suppression before complaints</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            {/* Agent Conflict Resolution */}
            <div className="mt-4 bg-blue-900/30 border border-blue-500/30 rounded-lg p-3">
              <div className="text-xs font-semibold text-blue-300 mb-2">🔀 When Agents Disagree</div>
              <div className="text-xs text-slate-300">
                <span className="text-slate-400">Example:</span> Offer Orchestration recommends Business ($199),
                but Channel Agent sees customer only has push notification consent (not ideal for $199 offer).
              </div>
              <div className="flex items-center gap-2 mt-2 text-xs">
                <div className="bg-blue-600 px-2 py-1 rounded">Conflict Detected</div>
                <span className="text-blue-400">→</span>
                <div className="bg-slate-700 px-2 py-1 rounded">State Updated</div>
                <span className="text-blue-400">→</span>
                <div className="bg-blue-600 px-2 py-1 rounded">Re-evaluate with MCE</div>
              </div>
              <div className="text-xs text-slate-400 mt-2">
                LangGraph conditional edges enable this loop-back without custom code
              </div>
            </div>
          </div>

          {/* Agent vs Rule Engine Comparison */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🧠 LLM Reasoning vs Rule Engine</h3>
            <div className="grid md:grid-cols-2 gap-4">
              {/* Rule Engine */}
              <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">⚙️</span>
                  <span className="font-semibold">Traditional Rule Engine</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span><code className="bg-slate-800 px-1 rounded">if P(buy) &gt; 0.5: send_offer()</code></span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Fixed thresholds, no context awareness</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Can't explain WHY a decision was made</span>
                  </li>
                </ul>
              </div>

              {/* LLM Reasoning */}
              <div className="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">🧠</span>
                  <span className="font-semibold">LLM Agent Reasoning</span>
                </div>
                <ul className="text-sm space-y-2 text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>"Given price sensitivity + inventory needs..."</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Holistic analysis of multiple factors</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>Full explainability and audit trail</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Key Message */}
          <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg p-4 text-center">
            <div className="text-lg font-semibold mb-1">
              💡 ML gives you a score. LLM Agents give you decisions + explanations.
            </div>
            <div className="text-sm text-slate-300">
              Same P(buy) = 0.73 → Different optimal actions for different customers based on context
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
