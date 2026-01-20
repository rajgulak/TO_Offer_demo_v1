import { useState } from 'react';

// Collapsible section component
function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-slate-600/30 bg-slate-900/50 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span>{icon}</span>
          <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
        </div>
        <span className={`text-sm transition-transform ${isOpen ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

interface ArchitectureOverviewProps {
  onOpenTutorial?: () => void;
}

export function ArchitectureOverview({ onOpenTutorial }: ArchitectureOverviewProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl shadow-lg text-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex-1 px-6 py-4 flex items-center justify-between hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-4">
            <span className="text-2xl">🏗️</span>
            <div className="text-left">
              <h2 className="font-semibold">Architecture</h2>
              <p className="text-sm text-slate-300">Production-Ready Agent Framework (Score: 88/100)</p>
            </div>
          </div>
          <span className={`text-xl transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
        </button>

        {/* Interactive Tutorial Button */}
        {onOpenTutorial && (
          <button
            onClick={onOpenTutorial}
            className="mr-4 px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500
                       rounded-lg font-medium text-sm shadow-lg hover:shadow-xl transition-all duration-300
                       flex items-center gap-2 animate-pulse hover:animate-none"
          >
            <span>🎓</span>
            <span>Take the Tour</span>
            <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">New!</span>
          </button>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-6 pb-6 space-y-4">

          {/* Pipeline Diagram */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="flex flex-col items-center gap-3 text-sm">
              <div className="flex items-center gap-2 w-full justify-center flex-wrap">
                <div className="bg-slate-600 px-3 py-2 rounded-lg text-center">
                  <div className="font-bold">⚡ Workflows</div>
                  <div className="text-xs opacity-80">4 steps</div>
                </div>
                <span className="text-slate-400">→</span>
                <div className="bg-blue-600 px-3 py-2 rounded-lg text-center border-2 border-blue-400">
                  <div className="font-bold">🧠 Agent</div>
                  <div className="text-xs opacity-80">1 step</div>
                </div>
                <span className="text-slate-400">→</span>
                <div className="bg-purple-600 px-3 py-2 rounded-lg text-center">
                  <div className="font-bold">✨ LLM Call</div>
                  <div className="text-xs opacity-80">1 step</div>
                </div>
              </div>
              <span className="text-slate-400">↓</span>
              <div className="bg-teal-600 px-4 py-2 rounded-lg text-center">
                <div className="font-bold">MCP Tools</div>
                <div className="text-xs opacity-80">Standard interface to existing systems</div>
              </div>
            </div>
          </div>

          {/* Decision Tree - When to use what */}
          <CollapsibleSection title="Decision Tree: Workflow vs Agent vs LLM Call" icon="🌳" defaultOpen={true}>
            <div className="space-y-4">
              {/* The Decision Tree */}
              <div className="bg-slate-800 rounded-lg p-4 font-mono text-sm">
                <div className="text-slate-400 mb-3"># For each step in your pipeline, ask:</div>
                <div className="space-y-2">
                  <div>
                    <span className="text-yellow-400">Does it need to EXPLAIN why?</span>
                  </div>
                  <div className="pl-4">
                    <span className="text-slate-500">├─</span>
                    <span className="text-red-400"> NO</span>
                    <span className="text-slate-400"> → Is it generative text?</span>
                  </div>
                  <div className="pl-8">
                    <span className="text-slate-500">├─</span>
                    <span className="text-emerald-400"> YES</span>
                    <span className="text-slate-400"> → </span>
                    <span className="text-purple-400">LLM Call</span>
                    <span className="text-slate-500"> (just generate, no reasoning)</span>
                  </div>
                  <div className="pl-8">
                    <span className="text-slate-500">└─</span>
                    <span className="text-red-400"> NO</span>
                    <span className="text-slate-400"> → </span>
                    <span className="text-slate-300">Workflow</span>
                    <span className="text-slate-500"> (just code, log the result)</span>
                  </div>
                  <div className="pl-4">
                    <span className="text-slate-500">└─</span>
                    <span className="text-emerald-400"> YES</span>
                    <span className="text-slate-400"> → </span>
                    <span className="text-blue-400">Agent</span>
                    <span className="text-slate-500"> (returns decision + reasoning)</span>
                  </div>
                </div>
              </div>

              {/* Applied to TO */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-700">
                      <th className="text-left py-2 px-2">Step</th>
                      <th className="text-left py-2 px-2">Needs to explain?</th>
                      <th className="text-left py-2 px-2">Generative?</th>
                      <th className="text-left py-2 px-2">Type</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-300">
                    <tr className="border-b border-slate-700/50">
                      <td className="py-2 px-2">Customer Intelligence</td>
                      <td className="py-2 px-2">No (yes/no check)</td>
                      <td className="py-2 px-2">No</td>
                      <td className="py-2 px-2"><span className="bg-slate-600 px-2 py-0.5 rounded text-xs">⚡ Workflow</span></td>
                    </tr>
                    <tr className="border-b border-slate-700/50">
                      <td className="py-2 px-2">Flight Optimization</td>
                      <td className="py-2 px-2">No (data lookup)</td>
                      <td className="py-2 px-2">No</td>
                      <td className="py-2 px-2"><span className="bg-slate-600 px-2 py-0.5 rounded text-xs">⚡ Workflow</span></td>
                    </tr>
                    <tr className="border-b border-slate-700/50 bg-blue-900/20">
                      <td className="py-2 px-2 font-semibold">Offer Orchestration</td>
                      <td className="py-2 px-2 text-blue-400">Yes (15+ factors)</td>
                      <td className="py-2 px-2">No</td>
                      <td className="py-2 px-2"><span className="bg-blue-600 px-2 py-0.5 rounded text-xs">🧠 Agent</span></td>
                    </tr>
                    <tr className="border-b border-slate-700/50">
                      <td className="py-2 px-2">Personalization</td>
                      <td className="py-2 px-2">No (just text)</td>
                      <td className="py-2 px-2 text-purple-400">Yes</td>
                      <td className="py-2 px-2"><span className="bg-purple-600 px-2 py-0.5 rounded text-xs">✨ LLM Call</span></td>
                    </tr>
                    <tr className="border-b border-slate-700/50">
                      <td className="py-2 px-2">Channel & Timing</td>
                      <td className="py-2 px-2">No (rule-based)</td>
                      <td className="py-2 px-2">No</td>
                      <td className="py-2 px-2"><span className="bg-slate-600 px-2 py-0.5 rounded text-xs">⚡ Workflow</span></td>
                    </tr>
                    <tr>
                      <td className="py-2 px-2">Measurement</td>
                      <td className="py-2 px-2">No (random A/B)</td>
                      <td className="py-2 px-2">No</td>
                      <td className="py-2 px-2"><span className="bg-slate-600 px-2 py-0.5 rounded text-xs">⚡ Workflow</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </CollapsibleSection>

          {/* Component Definitions */}
          <CollapsibleSection title="Component Definitions" icon="📦">
            <div className="grid md:grid-cols-3 gap-4">
              {/* Workflow */}
              <div className="bg-slate-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">⚡</span>
                  <span className="font-semibold text-slate-300">Workflow</span>
                </div>
                <div className="text-xs text-slate-400 space-y-2">
                  <p><strong>What:</strong> Regular code that does a task</p>
                  <p><strong>Returns:</strong> Data (e.g., <code className="bg-slate-700 px-1 rounded">{'{eligible: true}'}</code>)</p>
                  <p><strong>When:</strong> Simple checks, data lookups, rule-based logic</p>
                </div>
              </div>

              {/* Agent */}
              <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">🧠</span>
                  <span className="font-semibold text-blue-300">Agent</span>
                </div>
                <div className="text-xs text-slate-300 space-y-2">
                  <p><strong>What:</strong> Makes decisions that need explanation</p>
                  <p><strong>Returns:</strong> <code className="bg-slate-700 px-1 rounded">{'{decision, reasoning, data_used}'}</code></p>
                  <p><strong>When:</strong> Complex multi-factor decisions, audit trail needed</p>
                </div>
              </div>

              {/* LLM Call */}
              <div className="bg-purple-900/30 border border-purple-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">✨</span>
                  <span className="font-semibold text-purple-300">LLM Call</span>
                </div>
                <div className="text-xs text-slate-300 space-y-2">
                  <p><strong>What:</strong> Generates text output</p>
                  <p><strong>Returns:</strong> String (e.g., <code className="bg-slate-700 px-1 rounded">"Sarah, upgrade..."</code>)</p>
                  <p><strong>When:</strong> Personalized messages, summaries, creative content</p>
                </div>
              </div>
            </div>
          </CollapsibleSection>

          {/* How They Connect */}
          <CollapsibleSection title="How Components Connect" icon="🔗">
            <div className="space-y-4">
              <div className="bg-slate-800 rounded-lg p-4 font-mono text-xs">
                <div className="text-slate-500"># All components share state and use MCP Tools</div>
                <div className="mt-2 space-y-1">
                  <div><span className="text-slate-400">State</span> = {'{customer, flight, ml_scores, ...}'}</div>
                  <div className="mt-2"></div>
                  <div><span className="text-slate-500"># Workflow example</span></div>
                  <div><span className="text-amber-400">def</span> customer_intel(state):</div>
                  <div>    customer = <span className="text-teal-400">get_customer</span>(state.customer_id)  <span className="text-slate-500"># MCP Tool</span></div>
                  <div>    <span className="text-amber-400">return</span> {'{'}<span className="text-emerald-400">"eligible"</span>: <span className="text-amber-400">not</span> customer.suppressed{'}'}</div>
                  <div className="mt-2"></div>
                  <div><span className="text-slate-500"># Agent example</span></div>
                  <div><span className="text-amber-400">def</span> offer_orchestration(state):</div>
                  <div>    <span className="text-slate-500"># Complex decision with 15+ factors...</span></div>
                  <div>    <span className="text-amber-400">return</span> {'{'}</div>
                  <div>        <span className="text-emerald-400">"decision"</span>: <span className="text-emerald-400">"OFFER_BUSINESS"</span>,</div>
                  <div>        <span className="text-emerald-400">"reasoning"</span>: <span className="text-emerald-400">"High LTV + low load factor..."</span>,</div>
                  <div>        <span className="text-emerald-400">"data_used"</span>: [<span className="text-emerald-400">"AADV"</span>, <span className="text-emerald-400">"ML Model"</span>]</div>
                  <div>    {'}'}</div>
                  <div className="mt-2"></div>
                  <div><span className="text-slate-500"># LLM Call example</span></div>
                  <div><span className="text-amber-400">def</span> personalization(state):</div>
                  <div>    <span className="text-amber-400">return</span> <span className="text-teal-400">llm.generate</span>(<span className="text-emerald-400">"Write offer for {'{'}state.customer{'}'}"</span>)</div>
                </div>
              </div>

              <div className="flex items-center justify-center gap-2 text-xs py-2 flex-wrap">
                <div className="bg-slate-700 px-2 py-1 rounded">All Components</div>
                <span className="text-teal-400">→</span>
                <div className="bg-teal-600 px-2 py-1 rounded">MCP Tools</div>
                <span className="text-teal-400">→</span>
                <div className="bg-emerald-600 px-2 py-1 rounded">Existing Systems</div>
              </div>
            </div>
          </CollapsibleSection>

          {/* Orchestration Pattern */}
          <CollapsibleSection title="Orchestration: Hardcoded Graph (not LLM Supervisor)" icon="🔄">
            <div className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <div className="bg-red-900/30 rounded-lg p-3">
                  <div className="font-medium text-red-300 mb-2">❌ LLM Supervisor</div>
                  <ul className="text-slate-300 space-y-1 text-xs">
                    <li>• LLM decides what to call next</li>
                    <li>• Expensive (LLM call for every routing decision)</li>
                    <li>• Unpredictable execution order</li>
                  </ul>
                </div>
                <div className="bg-emerald-900/30 rounded-lg p-3">
                  <div className="font-medium text-emerald-300 mb-2">✅ Hardcoded Graph</div>
                  <ul className="text-slate-300 space-y-1 text-xs">
                    <li>• Code defines execution order</li>
                    <li>• LLM only called where needed</li>
                    <li>• Predictable, testable, debuggable</li>
                  </ul>
                </div>
              </div>

              <div className="bg-slate-800 rounded-lg p-3 font-mono text-xs">
                <div className="text-slate-500"># LangGraph defines the sequence - no LLM routing</div>
                <div className="mt-1">
                  <span className="text-slate-400">graph</span> = StateGraph()</div>
                <div><span className="text-slate-400">graph</span>.add_node(<span className="text-emerald-400">"customer_intel"</span>, customer_workflow)</div>
                <div><span className="text-slate-400">graph</span>.add_node(<span className="text-emerald-400">"flight_opt"</span>, flight_workflow)</div>
                <div><span className="text-slate-400">graph</span>.add_node(<span className="text-emerald-400">"offer"</span>, offer_agent)  <span className="text-slate-500"># Only agent</span></div>
                <div><span className="text-slate-400">graph</span>.add_node(<span className="text-emerald-400">"personalize"</span>, llm_call)</div>
                <div><span className="text-slate-400">graph</span>.add_edge(<span className="text-emerald-400">"customer_intel"</span>, <span className="text-emerald-400">"flight_opt"</span>)</div>
                <div><span className="text-slate-400">graph</span>.add_edge(<span className="text-emerald-400">"flight_opt"</span>, <span className="text-emerald-400">"offer"</span>)</div>
                <div><span className="text-slate-400">graph</span>.add_edge(<span className="text-emerald-400">"offer"</span>, <span className="text-emerald-400">"personalize"</span>)</div>
              </div>

              <div className="bg-indigo-900/30 border border-indigo-500/30 rounded-lg p-3 mt-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🎓</span>
                  <span className="text-sm text-indigo-300">
                    <strong>Take the Tour</strong> (Technical mode, Step 3) to see how the graph changes based on execution mode and HITL settings.
                  </span>
                </div>
              </div>
            </div>
          </CollapsibleSection>

          {/* Data Flow */}
          <CollapsibleSection title="Data Architecture" icon="📦">
            <div className="space-y-4">
              <div className="bg-slate-800 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-2">MCP Tools abstract data sources:</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-slate-400">
                        <th className="text-left py-1 px-2">Tool</th>
                        <th className="text-left py-1 px-2">Demo</th>
                        <th className="text-left py-1 px-2">Production</th>
                      </tr>
                    </thead>
                    <tbody className="text-slate-300">
                      <tr className="border-t border-slate-700">
                        <td className="py-1 px-2 font-mono text-teal-400">get_customer()</td>
                        <td className="py-1 px-2">customers.json</td>
                        <td className="py-1 px-2">Customer 360 API</td>
                      </tr>
                      <tr className="border-t border-slate-700">
                        <td className="py-1 px-2 font-mono text-teal-400">get_flight()</td>
                        <td className="py-1 px-2">flights.json</td>
                        <td className="py-1 px-2">DCSID</td>
                      </tr>
                      <tr className="border-t border-slate-700">
                        <td className="py-1 px-2 font-mono text-teal-400">get_ml_scores()</td>
                        <td className="py-1 px-2">ml_scores.json</td>
                        <td className="py-1 px-2">ML Model Serving</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="text-xs text-slate-400">
                Change only <code className="bg-slate-700 px-1 rounded">tools/data_tools.py</code> to swap demo → production. Zero component changes.
              </div>
            </div>
          </CollapsibleSection>

          {/* Production Safety - NEW */}
          <CollapsibleSection title="Production Safety (Score: 88/100)" icon="🛡️">
            <div className="space-y-4">
              <div className="grid md:grid-cols-4 gap-3">
                {/* Idempotency */}
                <div className="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">🔑</span>
                    <span className="font-semibold text-emerald-300 text-sm">Idempotency</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-1">
                    <p>Prevents duplicate processing</p>
                    <p className="text-slate-400">Same PNR + date = cached</p>
                  </div>
                </div>

                {/* Cost Tracking */}
                <div className="bg-amber-900/30 border border-amber-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">💰</span>
                    <span className="font-semibold text-amber-300 text-sm">Cost Tracking</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-1">
                    <p>Per-request LLM costs</p>
                    <p className="text-slate-400">Model-specific pricing</p>
                  </div>
                </div>

                {/* Alerting */}
                <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">🚨</span>
                    <span className="font-semibold text-red-300 text-sm">Alerting</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-1">
                    <p>Error & cost anomalies</p>
                    <p className="text-slate-400">Slack + PagerDuty</p>
                  </div>
                </div>

                {/* Human-in-the-Loop */}
                <div className="bg-pink-900/30 border border-pink-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">👤</span>
                    <span className="font-semibold text-pink-300 text-sm">Human-in-Loop</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-1">
                    <p>Approval workflow</p>
                    <p className="text-slate-400">Halt → Persist → Resume</p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-800 rounded-lg p-3 font-mono text-xs">
                <div className="text-slate-500"># Ultimate production workflow with HITL</div>
                <div><span className="text-amber-400">from</span> agents.workflow <span className="text-amber-400">import</span> run_offer_evaluation_with_hitl</div>
                <div className="mt-1">result = run_offer_evaluation_with_hitl(pnr=<span className="text-emerald-400">"ABC123"</span>)</div>
                <div className="text-slate-500"># May return "pending_approval" for high-value offers</div>
              </div>
            </div>
          </CollapsibleSection>

          {/* 3-Layer Guardrails - NEW */}
          <CollapsibleSection title="3-Layer Guardrails (Latency Optimized)" icon="🚧">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs mb-2">
                <span className="bg-red-500/20 text-red-300 px-2 py-1 rounded">Naive: +500ms</span>
                <span className="text-slate-400">vs</span>
                <span className="bg-emerald-500/20 text-emerald-300 px-2 py-1 rounded">3-Layer: +60ms</span>
              </div>

              <div className="space-y-2">
                {/* Layer 1 */}
                <div className="bg-blue-900/30 rounded-lg p-3 border-l-4 border-blue-500">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-blue-300 text-sm">Layer 1: Sync Pre-flight</span>
                    <span className="text-xs bg-blue-500/30 px-2 py-0.5 rounded">~60ms BLOCKING</span>
                  </div>
                  <div className="text-xs text-slate-300">
                    Input validation, suppression check, consent, rate limit, time-to-departure
                  </div>
                </div>

                {/* Layer 2 */}
                <div className="bg-purple-900/30 rounded-lg p-3 border-l-4 border-purple-500">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-purple-300 text-sm">Layer 2: Async Background</span>
                    <span className="text-xs bg-purple-500/30 px-2 py-0.5 rounded">~0ms PARALLEL</span>
                  </div>
                  <div className="text-xs text-slate-300">
                    Compliance logging, value validation, fairness check, offer fatigue
                  </div>
                </div>

                {/* Layer 3 */}
                <div className="bg-amber-900/30 rounded-lg p-3 border-l-4 border-amber-500">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-amber-300 text-sm">Layer 3: Triggered Escalation</span>
                    <span className="text-xs bg-amber-500/30 px-2 py-0.5 rounded">HUMAN-IN-LOOP</span>
                  </div>
                  <div className="text-xs text-slate-300">
                    High-value offers (&gt;$500), anomalies, regulatory flags, overrides
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleSection>

          {/* Agentic Patterns - NEW */}
          <CollapsibleSection title="Agentic Patterns" icon="🧠">
            <div className="space-y-4">
              <div className="grid md:grid-cols-2 gap-3">
                {/* Dual Execution */}
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-semibold text-slate-300 text-sm mb-2">Dual Execution Pattern</div>
                  <div className="text-xs space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">1.</span>
                      <span className="text-slate-300">Choreography (happy path)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-amber-400">2.</span>
                      <span className="text-slate-300">Planner-Worker (recovery)</span>
                    </div>
                    <div className="text-slate-400 mt-2 pt-2 border-t border-slate-700">
                      Toggle in Demo Controls & see flow in Workflow Visualization below
                    </div>
                  </div>
                </div>

                {/* Memory System */}
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-semibold text-slate-300 text-sm mb-2">4-Type Memory System</div>
                  <div className="text-xs space-y-1 text-slate-300">
                    <div>Conversation | Customer | Offer | Learning</div>
                    <div className="text-slate-400">Context-aware decisions</div>
                  </div>
                </div>

                {/* Feedback Loop */}
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-semibold text-slate-300 text-sm mb-2">Feedback Loop</div>
                  <div className="text-xs text-slate-300">
                    Outcome capture → Calibration → Agent learning
                  </div>
                </div>

                {/* Worker Recommendations */}
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="font-semibold text-slate-300 text-sm mb-2">Worker Recommendations</div>
                  <div className="text-xs text-slate-300 flex flex-wrap gap-1">
                    <span className="bg-slate-700 px-1.5 py-0.5 rounded">CONTINUE</span>
                    <span className="bg-slate-700 px-1.5 py-0.5 rounded">RETRY</span>
                    <span className="bg-slate-700 px-1.5 py-0.5 rounded">SIMPLIFY</span>
                    <span className="bg-slate-700 px-1.5 py-0.5 rounded">ESCALATE</span>
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleSection>

        </div>
      )}
    </div>
  );
}
