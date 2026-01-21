import { useState, useEffect } from 'react';

type Audience = 'business' | 'technical';
type ExecutionMode = 'choreography' | 'planner-worker';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function InteractiveTutorial({ isOpen, onClose }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [audience, setAudience] = useState<Audience>('business');
  const [animationPhase, setAnimationPhase] = useState(0);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('choreography');
  const [hitlEnabled, setHitlEnabled] = useState(false);

  const totalSteps = audience === 'business' ? 6 : 9;

  useEffect(() => {
    if (isOpen) {
      setAnimationPhase(0);
      const timer1 = setTimeout(() => setAnimationPhase(1), 300);
      const timer2 = setTimeout(() => setAnimationPhase(2), 800);
      const timer3 = setTimeout(() => setAnimationPhase(3), 1300);
      const timer4 = setTimeout(() => setAnimationPhase(4), 1800);
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        clearTimeout(timer4);
      };
    }
  }, [currentStep, isOpen]);

  useEffect(() => {
    if (isOpen) {
      setCurrentStep(0);
    }
  }, [isOpen]);

  const goToStep = (step: number) => {
    if (step >= 0 && step < totalSteps) {
      setAnimationPhase(0);
      setCurrentStep(step);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={onClose} />

      <div className="relative w-full max-w-5xl mx-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl shadow-2xl overflow-hidden border border-slate-700/50">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl ${
              audience === 'business'
                ? 'bg-gradient-to-br from-blue-500 to-purple-600'
                : 'bg-gradient-to-br from-emerald-500 to-cyan-600'
            }`}>
              {audience === 'business' ? '💼' : '⚙️'}
            </div>
            <div>
              <h2 className="font-bold text-white">
                {audience === 'business' ? 'Business Value Tour' : 'Technical Architecture Tour'}
              </h2>
              <p className="text-xs text-slate-400">Step {currentStep + 1} of {totalSteps}</p>
            </div>
          </div>

          {/* Audience Toggle */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-full p-1">
            <button
              onClick={() => { setAudience('business'); setCurrentStep(0); }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
                audience === 'business'
                  ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>💼</span> Business
            </button>
            <button
              onClick={() => { setAudience('technical'); setCurrentStep(0); }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
                audience === 'technical'
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-lg shadow-emerald-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>⚙️</span> Technical
            </button>
          </div>

          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white transition-colors">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content Area */}
        <div className="h-[520px] relative overflow-hidden">
          {audience === 'business' ? (
            <>
              {currentStep === 0 && <BusinessStep0 phase={animationPhase} />}
              {currentStep === 1 && <BusinessStep1 phase={animationPhase} />}
              {currentStep === 2 && <BusinessStep2 phase={animationPhase} />}
              {currentStep === 3 && <BusinessStep3 phase={animationPhase} />}
              {currentStep === 4 && <BusinessStep4 phase={animationPhase} />}
              {currentStep === 5 && <BusinessStep5 phase={animationPhase} />}
            </>
          ) : (
            <>
              {currentStep === 0 && <TechStep0 phase={animationPhase} />}
              {currentStep === 1 && <TechStep1 phase={animationPhase} />}
              {currentStep === 2 && <TechStep2 phase={animationPhase} executionMode={executionMode} setExecutionMode={setExecutionMode} hitlEnabled={hitlEnabled} setHitlEnabled={setHitlEnabled} />}
              {currentStep === 3 && <TechStep3 phase={animationPhase} />}
              {currentStep === 4 && <TechStepDataDecisions phase={animationPhase} />}
              {currentStep === 5 && <TechStep4 phase={animationPhase} />}
              {currentStep === 6 && <TechStep5 phase={animationPhase} />}
              {currentStep === 7 && <TechStep6 phase={animationPhase} />}
              {currentStep === 8 && <TechStep7 phase={animationPhase} />}
            </>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-700/50 bg-slate-900/50">
          <button
            onClick={() => goToStep(currentStep - 1)}
            disabled={currentStep === 0}
            className={`px-5 py-2 rounded-lg font-medium transition-all ${
              currentStep === 0 ? 'text-slate-600 cursor-not-allowed' : 'text-white bg-slate-700 hover:bg-slate-600'
            }`}
          >
            ← Back
          </button>

          <div className="flex gap-2">
            {Array.from({ length: totalSteps }).map((_, idx) => (
              <button
                key={idx}
                onClick={() => goToStep(idx)}
                className={`h-2 rounded-full transition-all duration-500 ${
                  idx === currentStep
                    ? `w-8 ${audience === 'business' ? 'bg-blue-500' : 'bg-emerald-500'}`
                    : idx < currentStep ? 'w-2 bg-slate-500' : 'w-2 bg-slate-700'
                }`}
              />
            ))}
          </div>

          {currentStep < totalSteps - 1 ? (
            <button
              onClick={() => goToStep(currentStep + 1)}
              className={`px-5 py-2 rounded-lg font-medium transition-all text-white shadow-lg ${
                audience === 'business'
                  ? 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500'
                  : 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500'
              }`}
            >
              Next →
            </button>
          ) : (
            <button
              onClick={onClose}
              className={`px-5 py-2 rounded-lg font-medium transition-all text-white shadow-lg ${
                audience === 'business'
                  ? 'bg-gradient-to-r from-blue-500 to-purple-600'
                  : 'bg-gradient-to-r from-emerald-500 to-teal-600'
              }`}
            >
              Start Demo →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// =====================================================
// BUSINESS STEPS - AI Augments Existing Systems
// =====================================================

function BusinessStep0({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-gradient-to-b from-blue-900/20 to-transparent">
      <div className={`transition-all duration-700 ${phase >= 1 ? 'scale-100 opacity-100' : 'scale-50 opacity-0'}`}>
        <div className="flex items-center gap-4 text-6xl mb-4">
          <span>🏢</span>
          <span className="text-blue-400">+</span>
          <span>🤖</span>
          <span className="text-blue-400">=</span>
          <span>💰</span>
        </div>
      </div>

      <h1 className={`text-4xl font-bold text-white text-center mb-4 transition-all duration-700 ${
        phase >= 2 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        AI-Powered, Human-Controlled
      </h1>

      <p className={`text-xl text-blue-200 text-center max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        AI orchestrates your <strong>existing systems</strong> - Customer 360, DCSID, ML Platform - to make personalized offers while humans stay in control
      </p>

      <div className={`mt-10 flex gap-6 transition-all duration-700 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { icon: '🎯', label: 'Your Data', desc: 'AI uses YOUR systems' },
          { icon: '🛡️', label: 'Your Rules', desc: 'AI follows YOUR constraints' },
          { icon: '👤', label: 'Your Control', desc: 'Humans approve high-value' },
        ].map((item, i) => (
          <div key={i} className="text-center bg-slate-800/50 rounded-xl p-4 w-40">
            <div className="text-3xl mb-2">{item.icon}</div>
            <div className="text-white font-medium">{item.label}</div>
            <div className="text-xs text-slate-400 mt-1">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BusinessStep1({ phase }: { phase: number }) {
  const systems = [
    {
      icon: '👤',
      name: 'Customer 360',
      color: 'blue',
      data: ['Loyalty tier', 'Flight history', 'Preferences', 'Past purchases'],
      desc: 'Complete customer profile'
    },
    {
      icon: '✈️',
      name: 'DCSID',
      color: 'amber',
      data: ['Seat inventory', 'Cabin loads', 'Flight status', 'Upgrade availability'],
      desc: 'Real-time flight data'
    },
    {
      icon: '📊',
      name: 'ML Platform',
      color: 'purple',
      data: ['Purchase probability', 'Price sensitivity', 'Churn risk', 'LTV score'],
      desc: 'Predictive models'
    },
  ];

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-3xl font-bold text-white mb-2 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Your Existing Enterprise Systems
      </h2>
      <p className={`text-slate-400 mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        AI doesn't replace these - it <strong className="text-blue-400">connects</strong> them intelligently
      </p>

      <div className="flex gap-6">
        {systems.map((sys, i) => (
          <div
            key={i}
            className={`transition-all duration-500`}
            style={{
              transitionDelay: `${i * 200}ms`,
              opacity: phase >= 2 ? 1 : 0,
              transform: phase >= 2 ? 'translateY(0)' : 'translateY(30px)',
            }}
          >
            <div className={`w-56 rounded-xl p-5 border-2 ${
              sys.color === 'blue' ? 'bg-blue-900/30 border-blue-500/50' :
              sys.color === 'amber' ? 'bg-amber-900/30 border-amber-500/50' :
              'bg-purple-900/30 border-purple-500/50'
            }`}>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-3xl">{sys.icon}</span>
                <div>
                  <div className="text-white font-bold">{sys.name}</div>
                  <div className="text-xs text-slate-400">{sys.desc}</div>
                </div>
              </div>
              <div className="space-y-1">
                {sys.data.map((d, j) => (
                  <div
                    key={j}
                    className={`text-xs px-2 py-1 rounded ${
                      sys.color === 'blue' ? 'bg-blue-800/50 text-blue-200' :
                      sys.color === 'amber' ? 'bg-amber-800/50 text-amber-200' :
                      'bg-purple-800/50 text-purple-200'
                    }`}
                    style={{
                      opacity: phase >= 3 ? 1 : 0,
                      transition: 'opacity 0.3s',
                      transitionDelay: `${800 + j * 100}ms`,
                    }}
                  >
                    {d}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className={`mt-8 bg-slate-800/50 rounded-xl px-6 py-3 transition-all duration-500 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        <span className="text-slate-300">These systems contain <strong className="text-emerald-400">billions of dollars</strong> of investment. AI amplifies their value.</span>
      </div>
    </div>
  );
}

function BusinessStep2({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* Systems on left */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="space-y-3">
          {[
            { icon: '👤', name: 'Customer 360', color: 'blue' },
            { icon: '✈️', name: 'DCSID', color: 'amber' },
            { icon: '📊', name: 'ML Platform', color: 'purple' },
          ].map((sys, i) => (
            <div
              key={i}
              className={`w-40 px-4 py-3 rounded-lg border text-center ${
                sys.color === 'blue' ? 'bg-blue-900/30 border-blue-500/50' :
                sys.color === 'amber' ? 'bg-amber-900/30 border-amber-500/50' :
                'bg-purple-900/30 border-purple-500/50'
              }`}
            >
              <span className="text-2xl mr-2">{sys.icon}</span>
              <span className="text-white text-sm font-medium">{sys.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Arrows */}
      <div className={`transition-all duration-500 delay-300 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col items-center gap-3">
          <div className="text-2xl text-slate-500 animate-pulse">→</div>
          <div className="text-2xl text-slate-500 animate-pulse" style={{ animationDelay: '0.2s' }}>→</div>
          <div className="text-2xl text-slate-500 animate-pulse" style={{ animationDelay: '0.4s' }}>→</div>
        </div>
      </div>

      {/* AI Orchestrator in middle */}
      <div className={`transition-all duration-700 delay-500 ${phase >= 2 ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}>
        <div className="relative">
          <div className="w-48 h-48 rounded-full bg-gradient-to-br from-emerald-600/30 to-cyan-600/30 flex items-center justify-center border-2 border-emerald-500/50 shadow-lg shadow-emerald-500/20">
            <div className="text-center">
              <div className="text-5xl mb-2">🤖</div>
              <div className="text-white font-bold">AI Orchestrator</div>
              <div className="text-xs text-emerald-300 mt-1">Connects the dots</div>
            </div>
          </div>

          {/* Thinking bubbles */}
          {phase >= 3 && (
            <>
              <div className="absolute -top-2 -right-16 bg-slate-700 rounded-lg px-2 py-1 text-[10px] text-slate-300 animate-bounce">
                "Gold member from 360..."
              </div>
              <div className="absolute top-12 -left-20 bg-slate-700 rounded-lg px-2 py-1 text-[10px] text-slate-300 animate-bounce" style={{ animationDelay: '0.3s' }}>
                "Cabin 70% full from DCSID..."
              </div>
              <div className="absolute -bottom-2 -right-12 bg-slate-700 rounded-lg px-2 py-1 text-[10px] text-slate-300 animate-bounce" style={{ animationDelay: '0.6s' }}>
                "High purchase probability..."
              </div>
            </>
          )}
        </div>
      </div>

      {/* Arrow */}
      <div className={`transition-all duration-500 delay-700 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="text-2xl text-emerald-500 animate-pulse">→</div>
      </div>

      {/* Result */}
      <div className={`transition-all duration-700 delay-700 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="bg-gradient-to-br from-emerald-900/50 to-teal-900/50 rounded-xl p-5 border-2 border-emerald-500/50 w-52">
          <div className="text-emerald-400 text-sm mb-2">Personalized Offer</div>
          <div className="text-xl font-bold text-white">Business @ $159</div>
          <div className="text-emerald-300 text-sm mt-1">20% discount</div>
          <div className="mt-3 pt-3 border-t border-emerald-500/30 text-xs text-slate-400">
            <div>Based on:</div>
            <div className="text-slate-300">• Customer 360 profile</div>
            <div className="text-slate-300">• DCSID inventory</div>
            <div className="text-slate-300">• ML predictions</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BusinessStep3({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-3xl font-bold text-white mb-2 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Humans Stay in Control
      </h2>
      <p className={`text-slate-400 mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        AI makes <strong className="text-amber-400">recommendations</strong>, humans make <strong className="text-emerald-400">final decisions</strong> on high-value offers
      </p>

      {/* HITL Flow */}
      <div className="flex items-center gap-4">
        {/* AI Recommendation */}
        <div className={`transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="bg-blue-900/30 border border-blue-500/50 rounded-xl p-4 w-44">
            <div className="text-2xl mb-2">🤖</div>
            <div className="text-white font-medium text-sm">AI Recommends</div>
            <div className="text-blue-300 text-xs mt-1">"$500 upgrade for VIP"</div>
          </div>
        </div>

        {/* Arrow with Check */}
        <div className={`transition-all duration-500 delay-200 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="flex flex-col items-center">
            <div className="text-amber-400 text-sm mb-1">Escalation Rule</div>
            <div className="text-2xl text-amber-400">→</div>
            <div className="text-xs text-slate-500">Value &gt; $400</div>
          </div>
        </div>

        {/* Human Review */}
        <div className={`transition-all duration-500 delay-400 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="bg-amber-900/30 border-2 border-amber-500/50 rounded-xl p-4 w-48 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-500 text-white text-xs px-2 py-0.5 rounded-full">
              PENDING APPROVAL
            </div>
            <div className="text-3xl mb-2 text-center">👤</div>
            <div className="text-white font-medium text-sm text-center">Revenue Manager</div>
            <div className="text-amber-300 text-xs mt-2 text-center">Reviews context, decides</div>
            <div className="flex gap-2 mt-3 justify-center">
              <button className="bg-emerald-600 text-white text-xs px-3 py-1 rounded">Approve</button>
              <button className="bg-red-600 text-white text-xs px-3 py-1 rounded">Deny</button>
            </div>
          </div>
        </div>

        {/* Arrow */}
        <div className={`transition-all duration-500 delay-600 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="text-2xl text-emerald-400">→</div>
        </div>

        {/* Final Action */}
        <div className={`transition-all duration-500 delay-600 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="bg-emerald-900/30 border border-emerald-500/50 rounded-xl p-4 w-44">
            <div className="text-2xl mb-2">✅</div>
            <div className="text-white font-medium text-sm">Offer Sent</div>
            <div className="text-emerald-300 text-xs mt-1">With human approval</div>
          </div>
        </div>
      </div>

      {/* Escalation Rules */}
      <div className={`mt-8 bg-slate-800/50 rounded-xl p-4 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="text-sm text-slate-400 mb-2">Backend-defined escalation rules (not AI decisions):</div>
        <div className="flex gap-4 text-xs">
          {[
            { rule: 'Offer > $400', icon: '💰' },
            { rule: 'VIP Customer', icon: '👑' },
            { rule: 'Regulatory Route', icon: '🌍' },
            { rule: 'Anomaly Detected', icon: '⚠️' },
          ].map((r, i) => (
            <div key={i} className="bg-slate-700/50 px-3 py-2 rounded">
              <span className="mr-1">{r.icon}</span>
              <span className="text-slate-300">{r.rule}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BusinessStep4({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-3xl font-bold text-white mb-2 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Always Within Your Constraints
      </h2>
      <p className={`text-slate-400 mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        3 layers of guardrails ensure AI never exceeds business rules
      </p>

      <div className="flex gap-6">
        {[
          {
            layer: 'Layer 1',
            name: 'Pre-Check',
            time: '~60ms',
            color: 'emerald',
            checks: ['Max discount limits', 'Customer eligibility', 'Inventory available'],
            icon: '🔍',
          },
          {
            layer: 'Layer 2',
            name: 'Parallel Validation',
            time: 'async',
            color: 'blue',
            checks: ['Compliance rules', 'Fraud detection', 'Rate limiting'],
            icon: '⚡',
          },
          {
            layer: 'Layer 3',
            name: 'Human Approval',
            time: 'triggered',
            color: 'amber',
            checks: ['High-value offers', 'VIP customers', 'Anomalies'],
            icon: '👤',
          },
        ].map((layer, i) => (
          <div
            key={i}
            className={`transition-all duration-500 w-52`}
            style={{
              transitionDelay: `${i * 200}ms`,
              opacity: phase >= 2 ? 1 : 0,
              transform: phase >= 2 ? 'translateY(0)' : 'translateY(20px)',
            }}
          >
            <div className={`rounded-xl p-4 border-2 ${
              layer.color === 'emerald' ? 'bg-emerald-900/20 border-emerald-500/50' :
              layer.color === 'blue' ? 'bg-blue-900/20 border-blue-500/50' :
              'bg-amber-900/20 border-amber-500/50'
            }`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-2xl">{layer.icon}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  layer.color === 'emerald' ? 'bg-emerald-500/30 text-emerald-300' :
                  layer.color === 'blue' ? 'bg-blue-500/30 text-blue-300' :
                  'bg-amber-500/30 text-amber-300'
                }`}>
                  {layer.time}
                </span>
              </div>
              <div className="text-white font-bold text-sm mb-1">{layer.name}</div>
              <div className="text-slate-400 text-xs mb-3">{layer.layer}</div>
              <div className="space-y-1">
                {layer.checks.map((check, j) => (
                  <div
                    key={j}
                    className={`text-xs px-2 py-1 rounded ${
                      layer.color === 'emerald' ? 'bg-emerald-800/30 text-emerald-200' :
                      layer.color === 'blue' ? 'bg-blue-800/30 text-blue-200' :
                      'bg-amber-800/30 text-amber-200'
                    }`}
                    style={{
                      opacity: phase >= 3 ? 1 : 0,
                      transition: 'opacity 0.3s',
                      transitionDelay: `${600 + j * 100}ms`,
                    }}
                  >
                    {check}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className={`mt-8 bg-slate-800/50 rounded-xl px-6 py-3 transition-all duration-500 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        <span className="text-slate-300">AI cannot bypass these rules - they're enforced in <strong className="text-emerald-400">backend code</strong>, not AI decisions</span>
      </div>
    </div>
  );
}

function BusinessStep5({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <div className={`text-6xl mb-4 transition-all duration-500 ${phase >= 1 ? 'scale-100' : 'scale-50'}`}>🎯</div>

      <h2 className={`text-3xl font-bold text-white mb-4 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        See It In Action
      </h2>

      <p className={`text-slate-400 mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Watch AI orchestrate your existing systems to create personalized offers
      </p>

      <div className={`flex gap-6 mb-8 transition-all duration-700 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { pnr: 'ABC123', name: 'Sarah', result: 'Business @ $171', status: 'Approved', color: 'emerald' },
          { pnr: 'JKL789', name: 'David', result: 'Business @ $499', status: 'Pending Approval', color: 'amber' },
          { pnr: 'GHI654', name: 'Lisa', result: 'No offer', status: 'Guardrail: Complaint', color: 'red' },
        ].map((scenario, i) => (
          <div
            key={i}
            className={`bg-slate-800 rounded-xl p-4 w-52 border-2 transition-all duration-500 hover:scale-105 cursor-pointer ${
              scenario.color === 'emerald' ? 'border-emerald-500/30 hover:border-emerald-500' :
              scenario.color === 'amber' ? 'border-amber-500/30 hover:border-amber-500' :
              'border-red-500/30 hover:border-red-500'
            }`}
            style={{ transitionDelay: `${i * 150}ms` }}
          >
            <div className="text-slate-400 font-mono text-sm">{scenario.pnr}</div>
            <div className="text-white font-bold mt-1">{scenario.name}</div>
            <div className={`text-sm mt-2 ${
              scenario.color === 'emerald' ? 'text-emerald-400' :
              scenario.color === 'amber' ? 'text-amber-400' :
              'text-red-400'
            }`}>
              {scenario.result}
            </div>
            <div className={`text-xs mt-2 px-2 py-1 rounded inline-block ${
              scenario.color === 'emerald' ? 'bg-emerald-900/30 text-emerald-300' :
              scenario.color === 'amber' ? 'bg-amber-900/30 text-amber-300' :
              'bg-red-900/30 text-red-300'
            }`}>
              {scenario.status}
            </div>
          </div>
        ))}
      </div>

      <div className={`flex items-center gap-4 bg-blue-900/20 rounded-xl px-6 py-4 border border-blue-500/30 transition-all duration-700 ${
        phase >= 3 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-4xl animate-bounce">👆</div>
        <div>
          <div className="text-white font-medium">Close this and try the demo!</div>
          <div className="text-blue-300 text-sm">Select a customer and click "Run Evaluation"</div>
        </div>
      </div>
    </div>
  );
}

// =====================================================
// TECHNICAL STEPS - Architecture, Patterns, ADRs
// =====================================================

function TechStep0({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-gradient-to-b from-emerald-900/20 to-transparent">
      <div className={`transition-all duration-700 ${phase >= 1 ? 'scale-100 opacity-100' : 'scale-50 opacity-0'}`}>
        <div className="font-mono text-6xl text-emerald-400">&lt;/&gt;</div>
      </div>

      <h1 className={`text-4xl font-bold text-white text-center mb-4 mt-6 transition-all duration-700 ${
        phase >= 2 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        Production-Ready Agentic Architecture
      </h1>

      <p className={`text-lg text-emerald-200 text-center max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        8 Architecture Decision Records (ADRs) covering patterns, guardrails, and production safety
      </p>

      <div className={`mt-10 grid grid-cols-4 gap-3 transition-all duration-700 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        {[
          { id: 'ADR-001', title: 'Workflow vs Agent', icon: '🧭' },
          { id: 'ADR-002', title: 'Execution Patterns', icon: '🔀' },
          { id: 'ADR-003', title: 'MCP Tools', icon: '🔌' },
          { id: 'ADR-004', title: '3-Layer Guardrails', icon: '🛡️' },
          { id: 'ADR-005', title: 'Memory System', icon: '🧠' },
          { id: 'ADR-006', title: 'Feedback Loop', icon: '📊' },
          { id: 'ADR-007', title: 'Production Safety', icon: '🔒' },
          { id: 'ADR-008', title: 'Human-in-Loop', icon: '👤' },
        ].map((adr, i) => (
          <div
            key={i}
            className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center hover:border-emerald-500/50 transition-colors"
          >
            <div className="text-xl mb-1">{adr.icon}</div>
            <div className="text-emerald-400 text-xs font-mono">{adr.id}</div>
            <div className="text-white text-xs mt-1">{adr.title}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TechStep1({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* Decision Framework */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">ADR-001: When to Use What?</h3>
        <div className="bg-slate-900 rounded-xl p-4 w-80">
          <div className="space-y-3">
            {[
              {
                type: 'Workflow',
                when: 'Deterministic, no reasoning needed',
                examples: ['Customer lookup', 'Inventory check', 'Channel selection'],
                color: 'slate',
                icon: '⚙️',
              },
              {
                type: 'Agent',
                when: 'Complex reasoning + constraints',
                examples: ['Offer selection', 'Price optimization', 'Recovery planning'],
                color: 'blue',
                icon: '🤖',
              },
              {
                type: 'LLM Call',
                when: 'Text generation only',
                examples: ['Message personalization', 'Explanation text'],
                color: 'purple',
                icon: '✍️',
              },
            ].map((item, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg border ${
                  item.color === 'slate' ? 'bg-slate-800/50 border-slate-600' :
                  item.color === 'blue' ? 'bg-blue-900/30 border-blue-500/50' :
                  'bg-purple-900/30 border-purple-500/50'
                }`}
                style={{
                  opacity: phase >= 2 ? 1 : 0,
                  transition: 'opacity 0.5s',
                  transitionDelay: `${i * 200}ms`,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span>{item.icon}</span>
                  <span className={`font-bold ${
                    item.color === 'slate' ? 'text-slate-300' :
                    item.color === 'blue' ? 'text-blue-300' :
                    'text-purple-300'
                  }`}>{item.type}</span>
                </div>
                <div className="text-xs text-slate-400 mb-2">{item.when}</div>
                <div className="flex flex-wrap gap-1">
                  {item.examples.map((ex, j) => (
                    <span key={j} className="text-[10px] bg-slate-700/50 text-slate-300 px-1.5 py-0.5 rounded">
                      {ex}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Pipeline Visualization */}
      <div className={`transition-all duration-700 delay-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">Our Pipeline: 4 Workflows + 1 Agent + 1 LLM</h3>
        <div className="flex items-center gap-2">
          {[
            { name: 'Customer', type: 'workflow', badge: null },
            { name: 'Flight', type: 'workflow', badge: null },
            { name: 'Offer', type: 'agent', badge: 'ReWOO' },
            { name: 'Message', type: 'llm', badge: null },
            { name: 'Channel', type: 'workflow', badge: null },
            { name: 'Measure', type: 'workflow', badge: null },
          ].map((node, i) => (
            <div key={i} className="flex items-center">
              <div className={`px-3 py-2 rounded-lg text-center ${
                node.type === 'workflow' ? 'bg-slate-700 border border-slate-600' :
                node.type === 'agent' ? 'bg-blue-600 border-2 border-blue-400' :
                'bg-purple-600 border border-purple-400'
              }`}>
                <div className="text-white text-xs font-medium">{node.name}</div>
                <div className={`text-[9px] mt-0.5 ${
                  node.type === 'workflow' ? 'text-slate-400' :
                  node.type === 'agent' ? 'text-blue-200' :
                  'text-purple-200'
                }`}>
                  {node.badge ? `${node.type} (${node.badge})` : node.type}
                </div>
              </div>
              {i < 5 && <span className="text-slate-600 mx-1">→</span>}
            </div>
          ))}
        </div>

        <div className={`mt-6 bg-slate-800/50 rounded-lg p-3 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="text-xs text-slate-400">
            <strong className="text-emerald-400">Key Insight:</strong> The Offer node uses <strong className="text-blue-400">ReWOO</strong> pattern
            (Planner → Worker → Solver) for structured reasoning with trade-offs.
            Other nodes are deterministic - faster, cheaper, predictable.
          </div>
        </div>
      </div>
    </div>
  );
}

interface TechStep2Props {
  phase: number;
  executionMode: ExecutionMode;
  setExecutionMode: (mode: ExecutionMode) => void;
  hitlEnabled: boolean;
  setHitlEnabled: (enabled: boolean) => void;
}

function TechStep2({ phase, executionMode, setExecutionMode, hitlEnabled, setHitlEnabled }: TechStep2Props) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-6 overflow-y-auto">
      <h2 className={`text-xl font-bold text-white mb-1 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        LangGraph Workflow Visualization
      </h2>
      <p className={`text-slate-400 text-sm mb-3 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Toggle options to see how the actual workflow graph changes
      </p>

      {/* Toggles Row */}
      <div className={`flex items-center gap-4 mb-4 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        {/* Execution Mode Toggle */}
        <div className="flex items-center gap-2 bg-slate-800 rounded-full p-1">
          <button
            onClick={() => setExecutionMode('choreography')}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              executionMode === 'choreography'
                ? 'bg-emerald-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            ⚡ Choreography
          </button>
          <button
            onClick={() => setExecutionMode('planner-worker')}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              executionMode === 'planner-worker'
                ? 'bg-amber-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            🧠 Planner-Worker
          </button>
        </div>

        {/* HITL Toggle */}
        <div className="flex items-center gap-2 bg-slate-800 rounded-full p-1">
          <button
            onClick={() => setHitlEnabled(false)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              !hitlEnabled
                ? 'bg-blue-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            🤖 Auto
          </button>
          <button
            onClick={() => setHitlEnabled(true)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              hitlEnabled
                ? 'bg-purple-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            👤 HITL
          </button>
        </div>
      </div>

      {/* LangGraph Flow Visualization */}
      <div className={`transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {executionMode === 'choreography' ? (
          <div className={`rounded-xl p-4 border-2 ${hitlEnabled ? 'bg-purple-900/10 border-purple-500/30' : 'bg-emerald-900/10 border-emerald-500/30'}`}>
            {/* Mode Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">⚡</span>
                <div>
                  <div className={`font-bold text-sm ${hitlEnabled ? 'text-purple-300' : 'text-emerald-300'}`}>
                    Sequential Choreography {hitlEnabled && '+ HITL'}
                  </div>
                  <div className="text-[10px] text-slate-400">Each node knows its next step via edges</div>
                </div>
              </div>
              <div className="text-xs text-slate-500">~{hitlEnabled ? '2-3s + approval' : '2-3s'}</div>
            </div>

            {/* Actual LangGraph Nodes */}
            <div className="bg-slate-900/50 rounded-lg p-3">
              {/* Row 1: Main Flow */}
              <div className="flex items-center justify-center gap-1 text-[10px]">
                <NodeBox label="START" type="start" />
                <Arrow />
                <NodeBox label="Load Data" type="workflow" />
                <Arrow />
                <NodeBox label="Customer" type="workflow" />
                <Arrow label="eligible" conditional />
                <NodeBox label="Flight" type="workflow" />
                <Arrow />
                <NodeBox label="Offer" type="agent" highlight />
                {hitlEnabled ? (
                  <>
                    <Arrow label="check" conditional />
                    <NodeBox label="HITL" type="hitl" highlight />
                    <Arrow label="approved" conditional />
                  </>
                ) : (
                  <Arrow />
                )}
                <NodeBox label="Message" type="llm" />
                <Arrow />
                <NodeBox label="Channel" type="workflow" />
                <Arrow />
                <NodeBox label="Measure" type="workflow" />
                <Arrow />
                <NodeBox label="Final" type="decision" />
                <Arrow />
                <NodeBox label="END" type="end" />
              </div>

              {/* Conditional Branches */}
              <div className="mt-2 flex justify-center gap-8 text-[9px]">
                <div className="flex items-center gap-1 text-amber-400">
                  <span>↳</span>
                  <span className="bg-amber-900/30 px-1.5 py-0.5 rounded">Customer ineligible → skip to Final</span>
                </div>
                {hitlEnabled && (
                  <div className="flex items-center gap-1 text-red-400">
                    <span>↳</span>
                    <span className="bg-red-900/30 px-1.5 py-0.5 rounded">HITL denied → suppress offer</span>
                  </div>
                )}
              </div>
            </div>

            {/* Info Cards */}
            <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]">
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-emerald-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-emerald-400'}>Edges</div>
                <div className="text-slate-300">add_edge() defines flow</div>
              </div>
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-emerald-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-emerald-400'}>Conditional</div>
                <div className="text-slate-300">add_conditional_edges()</div>
              </div>
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-emerald-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-emerald-400'}>{hitlEnabled ? 'HITL' : 'Resilient'}</div>
                <div className="text-slate-300">{hitlEnabled ? 'State persisted for resume' : 'Retry wrapper on each node'}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className={`rounded-xl p-4 border-2 ${hitlEnabled ? 'bg-purple-900/10 border-purple-500/30' : 'bg-amber-900/10 border-amber-500/30'}`}>
            {/* Mode Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">🧠</span>
                <div>
                  <div className={`font-bold text-sm ${hitlEnabled ? 'text-purple-300' : 'text-amber-300'}`}>
                    Planner-Worker Pattern {hitlEnabled && '+ HITL'}
                  </div>
                  <div className="text-[10px] text-slate-400">Planner LLM decides next step dynamically</div>
                </div>
              </div>
              <div className="text-xs text-slate-500">~5-10s (recovery)</div>
            </div>

            {/* Hub and Spoke Visualization */}
            <div className="bg-slate-900/50 rounded-lg p-3">
              <div className="flex items-center justify-center gap-2">
                {/* Entry */}
                <div className="flex items-center gap-1">
                  <NodeBox label="START" type="start" />
                  <Arrow />
                  <NodeBox label="Load" type="workflow" />
                  <Arrow />
                </div>

                {/* Planner Hub */}
                <div className="relative">
                  <div className="w-20 h-20 rounded-full bg-amber-900/30 border-2 border-amber-500/50 flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-lg">🎯</div>
                      <div className="text-[9px] text-amber-200 font-bold">Planner</div>
                    </div>
                  </div>

                  {/* Spokes to workers */}
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[8px] text-slate-400">decides next →</div>
                </div>

                {/* Workers */}
                <div className="flex flex-col gap-1 ml-2">
                  {[
                    { label: 'Customer', type: 'workflow' as const },
                    { label: 'Flight', type: 'workflow' as const },
                    { label: 'Offer', type: 'agent' as const },
                    { label: 'Message', type: 'llm' as const },
                  ].map((w, i) => (
                    <div key={i} className="flex items-center gap-1">
                      <span className="text-amber-500 text-[10px]">↔</span>
                      <NodeBox label={w.label} type={w.type} small />
                    </div>
                  ))}
                  {hitlEnabled && (
                    <div className="flex items-center gap-1">
                      <span className="text-purple-500 text-[10px]">↔</span>
                      <NodeBox label="HITL" type="hitl" small highlight />
                    </div>
                  )}
                </div>

                {/* Exit */}
                <div className="flex items-center gap-1 ml-2">
                  <Arrow label="done" />
                  <NodeBox label="Final" type="decision" />
                  <Arrow />
                  <NodeBox label="END" type="end" />
                </div>
              </div>

              <div className="mt-2 text-center text-[9px] text-slate-400">
                Workers report back → Planner decides next step or completion
              </div>
            </div>

            {/* Info Cards */}
            <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]">
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-amber-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-amber-400'}>Dynamic</div>
                <div className="text-slate-300">LLM chooses next worker</div>
              </div>
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-amber-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-amber-400'}>Recovery</div>
                <div className="text-slate-300">Can retry, simplify, escalate</div>
              </div>
              <div className={`rounded p-2 ${hitlEnabled ? 'bg-purple-800/20' : 'bg-amber-800/20'}`}>
                <div className={hitlEnabled ? 'text-purple-400' : 'text-amber-400'}>{hitlEnabled ? 'Escalation' : 'When'}</div>
                <div className="text-slate-300">{hitlEnabled ? 'Planner can trigger HITL' : 'Multiple failures detected'}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className={`mt-3 flex flex-wrap justify-center gap-3 text-[9px] transition-all duration-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-slate-700 border border-slate-500 rounded"></div>
          <span className="text-slate-400">Workflow</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-blue-900/50 border border-blue-500 rounded"></div>
          <span className="text-slate-400">Agent</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-purple-900/50 border border-purple-500 rounded"></div>
          <span className="text-slate-400">LLM Call</span>
        </div>
        {hitlEnabled && (
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-pink-900/50 border border-pink-500 rounded"></div>
            <span className="text-slate-400">HITL Checkpoint</span>
          </div>
        )}
        <div className="flex items-center gap-1">
          <span className="text-slate-500">──</span>
          <span className="text-slate-400">Edge</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-slate-500">╌╌</span>
          <span className="text-slate-400">Conditional</span>
        </div>
      </div>

      <div className={`mt-2 text-[10px] text-slate-500 transition-all duration-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        See: agents/workflow.py | create_workflow()
      </div>
    </div>
  );
}

// Helper components for the LangGraph visualization
function NodeBox({ label, type, highlight, small }: { label: string; type: 'start' | 'end' | 'workflow' | 'agent' | 'llm' | 'decision' | 'hitl'; highlight?: boolean; small?: boolean }) {
  const styles = {
    start: 'bg-slate-600 border-slate-400 text-slate-200',
    end: 'bg-slate-600 border-slate-400 text-slate-200',
    workflow: 'bg-slate-700 border-slate-500 text-slate-200',
    agent: 'bg-blue-900/50 border-blue-500 text-blue-200',
    llm: 'bg-purple-900/50 border-purple-500 text-purple-200',
    decision: 'bg-emerald-900/50 border-emerald-500 text-emerald-200',
    hitl: 'bg-pink-900/50 border-pink-500 text-pink-200',
  };

  return (
    <div className={`${small ? 'px-1.5 py-0.5' : 'px-2 py-1'} rounded border ${styles[type]} ${highlight ? 'ring-1 ring-offset-1 ring-offset-slate-900 ring-current' : ''}`}>
      <span className={small ? 'text-[8px]' : 'text-[10px]'}>{label}</span>
    </div>
  );
}

function Arrow({ label, conditional }: { label?: string; conditional?: boolean }) {
  return (
    <div className="flex flex-col items-center">
      {label && <span className="text-[8px] text-slate-500 -mb-0.5">{label}</span>}
      <span className={`text-[10px] ${conditional ? 'text-amber-500' : 'text-slate-500'}`}>
        {conditional ? '╌→' : '→'}
      </span>
    </div>
  );
}

function TechStep3({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* MCP Architecture */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">ADR-003: MCP Tool Abstraction</h3>
        <div className="bg-slate-900 rounded-xl p-4 w-80">
          <div className="text-xs text-slate-400 mb-3">Standard interface for all data sources</div>

          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left py-2">MCP Tool</th>
                <th className="text-left py-2">Demo</th>
                <th className="text-left py-2">Production</th>
              </tr>
            </thead>
            <tbody>
              {[
                { tool: 'get_customer()', demo: 'JSON file', prod: 'Customer 360 API' },
                { tool: 'get_flight()', demo: 'JSON file', prod: 'DCSID' },
                { tool: 'get_ml_scores()', demo: 'JSON file', prod: 'ML Platform' },
                { tool: 'get_offers()', demo: 'JSON file', prod: 'Offer Catalog' },
              ].map((row, i) => (
                <tr
                  key={i}
                  className="border-b border-slate-800"
                  style={{
                    opacity: phase >= 2 ? 1 : 0,
                    transition: 'opacity 0.3s',
                    transitionDelay: `${i * 100}ms`,
                  }}
                >
                  <td className="py-2 text-emerald-400 font-mono">{row.tool}</td>
                  <td className="py-2 text-slate-400">{row.demo}</td>
                  <td className="py-2 text-blue-400">{row.prod}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Benefit Visualization */}
      <div className={`transition-all duration-700 delay-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">Zero Code Changes to Production</h3>

        <div className="flex items-center gap-4">
          {/* Demo */}
          <div className="bg-slate-800 rounded-lg p-4 w-44">
            <div className="text-slate-400 text-xs mb-2">Demo Mode</div>
            <div className="font-mono text-xs">
              <div className="text-emerald-400">data/</div>
              <div className="text-slate-300 ml-2">customers.json</div>
              <div className="text-slate-300 ml-2">flights.json</div>
            </div>
          </div>

          {/* Arrow with swap */}
          <div className="flex flex-col items-center">
            <div className="text-xs text-slate-500 mb-1">Swap</div>
            <div className="text-2xl">⇄</div>
            <div className="text-xs text-emerald-400 mt-1">Same API</div>
          </div>

          {/* Production */}
          <div className="bg-blue-900/30 border border-blue-500/50 rounded-lg p-4 w-44">
            <div className="text-blue-400 text-xs mb-2">Production Mode</div>
            <div className="font-mono text-xs">
              <div className="text-blue-400">APIs/</div>
              <div className="text-slate-300 ml-2">Customer 360</div>
              <div className="text-slate-300 ml-2">DCSID</div>
            </div>
          </div>
        </div>

        <div className={`mt-4 bg-slate-800/50 rounded-lg p-3 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="text-xs text-slate-400">
            <strong className="text-emerald-400">File:</strong> tools/data_tools.py
            <br/>
            <strong className="text-emerald-400">Config:</strong> tools/mcp_config.json
          </div>
        </div>
      </div>
    </div>
  );
}

function TechStepDataDecisions({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-6 overflow-y-auto">
      <h2 className={`text-xl font-bold text-white mb-1 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Demo Data: Mapped from Real Systems
      </h2>
      <p className={`text-slate-400 text-sm mb-4 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Data fields sourced from <span className="text-emerald-400">Tailored Offers Data Mapping</span> master document
      </p>

      <div className={`flex gap-4 transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {/* Customer Data Column */}
        <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-3 w-72">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">👤</span>
            <span className="text-blue-300 font-bold text-sm">Customer Data</span>
            <span className="text-[9px] bg-blue-800/50 text-blue-300 px-1.5 py-0.5 rounded">AADV Database</span>
          </div>
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left py-1">Demo Field</th>
                <th className="text-left py-1">Source</th>
              </tr>
            </thead>
            <tbody>
              {[
                { field: 'lylty_acct_id', source: 'LYLTY_ACCT_ID', priority: '1' },
                { field: 'loyalty_tier', source: 'LYLTY_TIER_CD', priority: '1' },
                { field: 'aadv_tenure_days', source: 'PGM_ENROLL_DT (derived)', priority: '1.5' },
                { field: 'home_airport_cd', source: 'HOME_AIRPRT_IATA_CD', priority: '1' },
                { field: 'flight_revenue_amt', source: 'FLIT_REV_AMT_12M', priority: '1' },
                { field: 'cobrand_cardholder', source: 'COBRD_CRDHLD_IND', priority: '1.5' },
              ].map((row, i) => (
                <tr key={i} className="border-b border-slate-800/50">
                  <td className="py-1 text-emerald-400 font-mono">{row.field}</td>
                  <td className="py-1 text-slate-400">{row.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* PNR/Trip Data Column */}
        <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-3 w-72">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">✈️</span>
            <span className="text-amber-300 font-bold text-sm">PNR / Trip Data</span>
            <span className="text-[9px] bg-amber-800/50 text-amber-300 px-1.5 py-0.5 rounded">DCSID + PSR</span>
          </div>
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left py-1">Demo Field</th>
                <th className="text-left py-1">Source</th>
              </tr>
            </thead>
            <tbody>
              {[
                { field: 'pnr_loctr_id', source: 'PNR_LOCTR_ID', priority: '1' },
                { field: 'origin_airport', source: 'POINT_OF_ORIGIN_IATA_CD', priority: '1' },
                { field: 'dest_airport', source: 'ACTL_LEG_ARVL_IATA_CD', priority: '1' },
                { field: 'intl_trp_ind', source: 'INTL_TRP_IND', priority: '1' },
                { field: 'max_bkd_cabin_cd', source: 'MAX_BKD_CABIN_CD', priority: '1' },
                { field: 'fare_class', source: 'FARE_CLS_CD', priority: '1' },
              ].map((row, i) => (
                <tr key={i} className="border-b border-slate-800/50">
                  <td className="py-1 text-emerald-400 font-mono">{row.field}</td>
                  <td className="py-1 text-slate-400">{row.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Why These Scenarios */}
      <div className={`mt-4 bg-slate-800/50 rounded-xl p-3 max-w-xl transition-all duration-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="text-sm text-white mb-2">Why These Demo Scenarios?</div>
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          {[
            { scenario: 'ABC123 (Sarah)', why: 'Easy choice - tests baseline EV calculation', icon: '✅' },
            { scenario: 'XYZ789 (John)', why: 'Confidence trade-off - unreliable ML prediction', icon: '🎯' },
            { scenario: 'LMN456 (Emily)', why: 'Relationship trade-off - recent service issue', icon: '💔' },
            { scenario: 'DEF321 (Michael)', why: 'Guardrail test - 0 seats available', icon: '🚫' },
            { scenario: 'GHI654 (Lisa)', why: 'Guardrail test - customer suppressed', icon: '⛔' },
            { scenario: 'JKL789 (David)', why: 'Price trade-off - high price sensitivity', icon: '💰' },
          ].map((s, i) => (
            <div key={i} className="bg-slate-700/30 rounded p-2">
              <div className="flex items-center gap-1">
                <span>{s.icon}</span>
                <span className="text-emerald-400 font-mono">{s.scenario}</span>
              </div>
              <div className="text-slate-400 mt-1">{s.why}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Reference */}
      <div className={`mt-3 text-[10px] text-slate-500 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        <span className="text-emerald-400">Reference:</span> Tailored Offers Data Mapping - All Groups - Master.xlsx | Priority 1 & 1.5 fields
      </div>
    </div>
  );
}

function TechStep4({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-2xl font-bold text-white mb-2 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        ADR-004: 3-Layer Guardrail Architecture
      </h2>
      <p className={`text-slate-400 mb-6 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Defense in depth - every request passes through all layers
      </p>

      {/* Flow Diagram */}
      <div className={`flex items-center gap-4 transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {/* Request */}
        <div className="bg-slate-700 rounded-lg p-3 text-center">
          <div className="text-xl mb-1">📥</div>
          <div className="text-white text-xs">Request</div>
        </div>

        <div className="text-slate-500">→</div>

        {/* Layer 1 */}
        <div className="bg-emerald-900/30 border-2 border-emerald-500/50 rounded-lg p-3 w-36">
          <div className="text-emerald-400 text-xs font-bold mb-1">Layer 1: Sync</div>
          <div className="text-xs text-slate-300">~60ms</div>
          <div className="mt-2 space-y-1 text-[10px] text-emerald-200">
            <div>• Eligibility check</div>
            <div>• Inventory exists</div>
            <div>• No recent complaint</div>
          </div>
        </div>

        <div className="text-emerald-500">→</div>

        {/* Layer 2 */}
        <div className="bg-blue-900/30 border-2 border-blue-500/50 rounded-lg p-3 w-36">
          <div className="text-blue-400 text-xs font-bold mb-1">Layer 2: Async</div>
          <div className="text-xs text-slate-300">parallel</div>
          <div className="mt-2 space-y-1 text-[10px] text-blue-200">
            <div>• Fraud detection</div>
            <div>• Compliance check</div>
            <div>• Rate limiting</div>
          </div>
        </div>

        <div className="text-blue-500">→</div>

        {/* Processing */}
        <div className="bg-purple-900/30 border border-purple-500/50 rounded-lg p-3">
          <div className="text-xl mb-1">🤖</div>
          <div className="text-purple-300 text-xs">Agent</div>
        </div>

        <div className="text-purple-500">→</div>

        {/* Layer 3 */}
        <div className="bg-amber-900/30 border-2 border-amber-500/50 rounded-lg p-3 w-36">
          <div className="text-amber-400 text-xs font-bold mb-1">Layer 3: Triggered</div>
          <div className="text-xs text-slate-300">conditional</div>
          <div className="mt-2 space-y-1 text-[10px] text-amber-200">
            <div>• High-value offer</div>
            <div>• VIP customer</div>
            <div>• Anomaly detected</div>
          </div>
        </div>

        <div className="text-amber-500">→</div>

        {/* Output */}
        <div className="bg-emerald-700 rounded-lg p-3 text-center">
          <div className="text-xl mb-1">✅</div>
          <div className="text-white text-xs">Offer</div>
        </div>
      </div>

      {/* Code Reference */}
      <div className={`mt-6 bg-slate-900 rounded-xl p-4 font-mono text-xs max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-slate-500"># infrastructure/guardrails.py</div>
        <div className="text-emerald-400">class <span className="text-white">ThreeLayerGuardrails</span>:</div>
        <div className="text-slate-400 ml-4">sync_check(state)    <span className="text-slate-600"># ~60ms, blocks</span></div>
        <div className="text-slate-400 ml-4">async_check(state)   <span className="text-slate-600"># parallel, non-blocking</span></div>
        <div className="text-slate-400 ml-4">trigger_check(offer) <span className="text-slate-600"># post-agent, may escalate</span></div>
      </div>

      <div className={`mt-4 text-xs text-slate-500 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        Total sync latency: ~60ms | Any layer can block the request
      </div>
    </div>
  );
}

function TechStep5({ phase }: { phase: number }) {
  const [hitlStep, setHitlStep] = useState(0);

  useEffect(() => {
    if (phase >= 2) {
      const interval = setInterval(() => {
        setHitlStep(prev => (prev + 1) % 5);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [phase]);

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-2xl font-bold text-white mb-2 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        ADR-008: Human-in-the-Loop (HITL)
      </h2>
      <p className={`text-slate-400 mb-6 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Deferred execution with state persistence for human approval
      </p>

      {/* HITL Flow */}
      <div className={`flex items-start gap-3 transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { step: 0, icon: '🤖', label: 'Agent Creates Offer', desc: 'Evaluates all factors' },
          { step: 1, icon: '⚠️', label: 'Escalation Triggered', desc: 'Backend rules check' },
          { step: 2, icon: '💾', label: 'State Persisted', desc: 'Full context saved' },
          { step: 3, icon: '👤', label: 'Human Reviews', desc: 'Approve/Deny/Modify' },
          { step: 4, icon: '▶️', label: 'Resume Execution', desc: 'Stateless continuation' },
        ].map((s, i) => (
          <div key={i} className="flex flex-col items-center">
            <div className={`w-24 h-24 rounded-xl flex flex-col items-center justify-center transition-all duration-300 ${
              hitlStep === s.step
                ? 'bg-amber-500/30 border-2 border-amber-400 scale-110'
                : 'bg-slate-800 border border-slate-700'
            }`}>
              <div className="text-2xl mb-1">{s.icon}</div>
              <div className={`text-[10px] text-center px-1 ${hitlStep === s.step ? 'text-amber-200' : 'text-slate-400'}`}>
                {s.label}
              </div>
            </div>
            <div className="text-[9px] text-slate-500 mt-1 text-center w-24">{s.desc}</div>
            {i < 4 && (
              <div className="absolute mt-12 ml-24">
                <span className={`text-sm ${hitlStep > s.step ? 'text-emerald-400' : 'text-slate-600'}`}>→</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Escalation Rules */}
      <div className={`mt-6 bg-slate-800/50 rounded-xl p-4 transition-all duration-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="text-sm text-white mb-2">Backend Escalation Rules (not LLM decisions):</div>
        <div className="grid grid-cols-4 gap-3 text-xs">
          {[
            { rule: 'Offer > $500', code: 'high_value_threshold' },
            { rule: 'VIP Tiers', code: 'vip_tiers = ["ConciergeKey"]' },
            { rule: 'Anomaly Score > 0.8', code: 'anomaly_threshold' },
            { rule: 'Regulatory Routes', code: 'regulatory_routes = ["EU"]' },
          ].map((r, i) => (
            <div key={i} className="bg-slate-700/50 rounded p-2">
              <div className="text-amber-400">{r.rule}</div>
              <div className="text-slate-500 font-mono text-[10px] mt-1">{r.code}</div>
            </div>
          ))}
        </div>
      </div>

      {/* API Endpoints */}
      <div className={`mt-4 font-mono text-xs text-slate-400 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        <span className="text-emerald-400">API:</span> /api/approvals/pending | /api/approvals/{'{id}'}/approve | /api/approvals/{'{id}'}/resume
      </div>
    </div>
  );
}

function TechStep6({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* Production Safety */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">ADR-007: Production Safety</h3>
        <div className="space-y-3 w-72">
          {[
            {
              icon: '🔑',
              title: 'Idempotency',
              desc: 'No duplicate offers to same customer',
              code: 'IdempotencyStore.check(pnr, offer_type)',
            },
            {
              icon: '💰',
              title: 'Cost Tracking',
              desc: 'Per-request LLM cost tracking',
              code: 'CostTracker.track(tokens, model)',
            },
            {
              icon: '🚨',
              title: 'Alerting',
              desc: 'Error rate anomaly detection',
              code: 'AlertManager.check_threshold()',
            },
          ].map((item, i) => (
            <div
              key={i}
              className="bg-slate-800 rounded-lg p-3 border border-slate-700"
              style={{
                opacity: phase >= 2 ? 1 : 0,
                transition: 'opacity 0.5s',
                transitionDelay: `${i * 150}ms`,
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span>{item.icon}</span>
                <span className="text-white font-medium text-sm">{item.title}</span>
              </div>
              <div className="text-xs text-slate-400 mb-2">{item.desc}</div>
              <div className="font-mono text-[10px] text-emerald-400 bg-slate-900 rounded px-2 py-1">
                {item.code}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Memory & Feedback */}
      <div className={`transition-all duration-700 delay-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-lg font-bold text-white mb-4">ADR-005/006: Memory & Feedback</h3>
        <div className="space-y-3 w-72">
          {[
            {
              icon: '🧠',
              title: 'Dual Memory',
              desc: 'Short-term (session) + Long-term (persistent)',
              items: ['Recent interactions', 'Customer preferences', 'Offer history'],
            },
            {
              icon: '📊',
              title: 'Feedback Loop',
              desc: 'Continuous improvement from outcomes',
              items: ['Track accept/reject', 'Update ML models', 'Adjust thresholds'],
            },
          ].map((item, i) => (
            <div
              key={i}
              className="bg-slate-800 rounded-lg p-3 border border-slate-700"
              style={{
                opacity: phase >= 3 ? 1 : 0,
                transition: 'opacity 0.5s',
                transitionDelay: `${300 + i * 150}ms`,
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span>{item.icon}</span>
                <span className="text-white font-medium text-sm">{item.title}</span>
              </div>
              <div className="text-xs text-slate-400 mb-2">{item.desc}</div>
              <div className="space-y-1">
                {item.items.map((it, j) => (
                  <div key={j} className="text-[10px] text-slate-300 flex items-center gap-1">
                    <span className="text-emerald-400">•</span> {it}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TechStep7({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <div className={`font-mono text-3xl text-emerald-400 mb-3 transition-all duration-500 ${phase >= 1 ? 'scale-100' : 'scale-50'}`}>
        Production Score: 88/100
      </div>

      <h2 className={`text-xl font-bold text-white mb-6 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Complete ADR Summary
      </h2>

      {/* ADR Grid */}
      <div className={`grid grid-cols-4 gap-3 mb-6 transition-all duration-700 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { id: 'ADR-001', title: 'Decision Framework', desc: 'Workflow vs Agent vs LLM', icon: '🧭', file: 'workflow.py' },
          { id: 'ADR-002', title: 'Execution Patterns', desc: 'Choreography + Planner-Worker', icon: '🔀', file: 'workflow.py' },
          { id: 'ADR-003', title: 'MCP Tools', desc: 'Abstraction over data sources', icon: '🔌', file: 'data_tools.py' },
          { id: 'ADR-004', title: '3-Layer Guardrails', desc: 'Sync + Async + Triggered', icon: '🛡️', file: 'guardrails.py' },
          { id: 'ADR-005', title: 'Memory System', desc: 'Short-term + Long-term', icon: '🧠', file: 'memory.py' },
          { id: 'ADR-006', title: 'Feedback Loop', desc: 'Continuous improvement', icon: '📊', file: 'feedback.py' },
          { id: 'ADR-007', title: 'Production Safety', desc: 'Idempotency + Cost + Alerts', icon: '🔒', file: 'production_safety.py' },
          { id: 'ADR-008', title: 'Human-in-Loop', desc: 'Deferred execution + Approval', icon: '👤', file: 'human_in_loop.py' },
        ].map((adr, i) => (
          <div
            key={i}
            className="bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-emerald-500/50 transition-colors"
            style={{ transitionDelay: `${i * 50}ms` }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{adr.icon}</span>
              <span className="text-emerald-400 text-xs font-mono">{adr.id}</span>
            </div>
            <div className="text-white text-sm font-medium">{adr.title}</div>
            <div className="text-slate-400 text-xs mt-1">{adr.desc}</div>
            <div className="text-slate-500 text-[10px] font-mono mt-2">{adr.file}</div>
          </div>
        ))}
      </div>

      {/* Entry Points */}
      <div className={`bg-slate-900 rounded-xl p-4 font-mono text-xs transition-all duration-700 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="text-slate-500 mb-2"># Entry points in agents/workflow.py</div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-emerald-400">run_offer_evaluation()</div>
            <div className="text-slate-500 text-[10px]">Standard evaluation</div>
          </div>
          <div>
            <div className="text-blue-400">run_offer_evaluation_production()</div>
            <div className="text-slate-500 text-[10px]">Full safety stack</div>
          </div>
          <div>
            <div className="text-amber-400">run_offer_evaluation_with_hitl()</div>
            <div className="text-slate-500 text-[10px]">Human-in-loop enabled</div>
          </div>
          <div>
            <div className="text-purple-400">resume_after_approval()</div>
            <div className="text-slate-500 text-[10px]">Continue after HITL</div>
          </div>
        </div>
      </div>

      <div className={`mt-4 flex items-center gap-4 bg-emerald-900/20 rounded-xl px-6 py-3 border border-emerald-500/30 transition-all duration-700 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-2xl">🚀</div>
        <div>
          <div className="text-white font-medium text-sm">Full documentation: ARCHITECTURE_DECISIONS.md</div>
          <div className="text-emerald-300 text-xs">Try the demo to see these patterns in action!</div>
        </div>
      </div>
    </div>
  );
}
