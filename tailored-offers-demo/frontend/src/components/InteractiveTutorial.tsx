import { useState, useEffect } from 'react';

type Audience = 'business' | 'technical';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function InteractiveTutorial({ isOpen, onClose }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [audience, setAudience] = useState<Audience>('business');
  const [animationPhase, setAnimationPhase] = useState(0);

  const totalSteps = 6;

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
              onClick={() => setAudience('business')}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
                audience === 'business'
                  ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>💼</span> Business
            </button>
            <button
              onClick={() => setAudience('technical')}
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
              {currentStep === 2 && <TechStep2 phase={animationPhase} />}
              {currentStep === 3 && <TechStep3 phase={animationPhase} />}
              {currentStep === 4 && <TechStep4 phase={animationPhase} />}
              {currentStep === 5 && <TechStep5 phase={animationPhase} />}
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
// BUSINESS STEPS - Focus on ROI, Revenue, Simple Metaphors
// =====================================================

function BusinessStep0({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-gradient-to-b from-blue-900/20 to-transparent">
      <div className={`transition-all duration-700 ${phase >= 1 ? 'scale-100 opacity-100' : 'scale-50 opacity-0'}`}>
        <div className="text-8xl mb-4">💰</div>
      </div>

      <h1 className={`text-5xl font-bold text-white text-center mb-4 transition-all duration-700 ${
        phase >= 2 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        Turn Every Offer Into Revenue
      </h1>

      <p className={`text-xl text-blue-200 text-center max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        See how AI makes smarter decisions than any rule book ever could
      </p>

      <div className={`mt-12 flex gap-6 transition-all duration-700 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { num: '2-3x', label: 'More Conversions' },
          { num: '$10M+', label: 'Annual Impact' },
          { num: '0', label: 'Manual Rules' },
        ].map((stat, i) => (
          <div key={i} className="text-center" style={{ animation: `fadeInUp 0.5s ease-out ${i * 0.15}s forwards` }}>
            <div className="text-3xl font-bold text-blue-400">{stat.num}</div>
            <div className="text-sm text-slate-400">{stat.label}</div>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function BusinessStep1({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-16">
      {/* The Problem Visual */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="relative w-64 h-72">
          {/* Spray and Pray Visual */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-6xl">📢</div>
          </div>

          {/* Scattered offers */}
          {phase >= 2 && ['↗', '→', '↘', '↓', '↙', '←', '↖', '↑'].map((arrow, i) => (
            <div
              key={i}
              className="absolute text-2xl text-red-400"
              style={{
                top: '50%',
                left: '50%',
                animation: `scatter 1s ease-out ${i * 0.1}s forwards`,
                transform: `rotate(${i * 45}deg)`,
              }}
            >
              {arrow}
            </div>
          ))}

          {/* Sad conversion */}
          <div className={`absolute bottom-0 left-1/2 -translate-x-1/2 transition-all duration-500 ${
            phase >= 3 ? 'opacity-100' : 'opacity-0'
          }`}>
            <div className="bg-red-500/20 border border-red-500/50 rounded-xl px-4 py-2 text-center">
              <div className="text-2xl font-bold text-red-400">2-5%</div>
              <div className="text-xs text-red-300">say yes</div>
            </div>
          </div>
        </div>
      </div>

      {/* Problem Description */}
      <div className={`max-w-md transition-all duration-700 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        <h2 className="text-3xl font-bold text-white mb-6">The "Spray & Pray" Problem</h2>

        <div className="space-y-4">
          {[
            { icon: '📋', text: 'Same offer to everyone', sub: 'Gold member = New member?' },
            { icon: '💸', text: 'Wrong price', sub: 'Too high? Too low?' },
            { icon: '⏰', text: 'Wrong time', sub: 'Annoying customers at 3am' },
          ].map((item, i) => (
            <div
              key={i}
              className={`flex items-start gap-4 bg-slate-800/50 rounded-lg p-3 transition-all duration-500`}
              style={{ transitionDelay: `${300 + i * 200}ms`, opacity: phase >= 3 ? 1 : 0 }}
            >
              <span className="text-2xl">{item.icon}</span>
              <div>
                <div className="text-white font-medium">{item.text}</div>
                <div className="text-slate-400 text-sm">{item.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes scatter {
          to { transform: translateX(calc(cos(var(--angle)) * 80px)) translateY(calc(sin(var(--angle)) * 80px)); opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

function BusinessStep2({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="flex items-center gap-8">
        {/* Before */}
        <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}>
          <div className="w-56 bg-slate-800 rounded-2xl p-6 text-center border-2 border-red-500/30">
            <div className="text-5xl mb-3">🤖</div>
            <div className="text-lg font-bold text-white mb-2">Old Way</div>
            <div className="text-sm text-slate-400 mb-4">"If Gold member, offer $199"</div>
            <div className="text-red-400 font-mono text-xs bg-red-900/20 rounded p-2">
              1,000 rules... still dumb
            </div>
          </div>
        </div>

        {/* Arrow */}
        <div className={`transition-all duration-500 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="text-4xl text-emerald-400 animate-pulse">→</div>
        </div>

        {/* After */}
        <div className={`transition-all duration-700 delay-300 ${phase >= 2 ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}>
          <div className="w-56 bg-gradient-to-br from-blue-900/50 to-purple-900/50 rounded-2xl p-6 text-center border-2 border-blue-500/50 shadow-lg shadow-blue-500/20">
            <div className="text-5xl mb-3">🧠</div>
            <div className="text-lg font-bold text-white mb-2">New Way</div>
            <div className="text-sm text-blue-200 mb-4">"Let me think about this..."</div>
            <div className="text-emerald-400 font-medium bg-emerald-900/20 rounded p-2 text-sm">
              Weighs 15+ factors
            </div>
          </div>
        </div>

        {/* Result */}
        <div className={`transition-all duration-700 delay-500 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
          <div className="text-4xl text-emerald-400 animate-pulse">=</div>
        </div>

        <div className={`transition-all duration-700 delay-700 ${phase >= 4 ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}>
          <div className="w-56 bg-gradient-to-br from-emerald-900/50 to-teal-900/50 rounded-2xl p-6 text-center border-2 border-emerald-500/50">
            <div className="text-5xl mb-3">📈</div>
            <div className="text-lg font-bold text-white mb-2">Results</div>
            <div className="space-y-2 text-left">
              <div className="flex justify-between">
                <span className="text-slate-400">Conversion</span>
                <span className="text-emerald-400 font-bold">+150%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Revenue</span>
                <span className="text-emerald-400 font-bold">+$10M</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Complaints</span>
                <span className="text-emerald-400 font-bold">-40%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BusinessStep3({ phase }: { phase: number }) {
  const team = [
    { icon: '👤', name: 'Scout', job: 'Checks if we should call', desc: 'Recent complaint? Don\'t bother them.' },
    { icon: '✈️', name: 'Inventory', job: 'Checks what\'s available', desc: 'Business full? Try Premium.' },
    { icon: '🧠', name: 'Strategist', job: 'Picks the best offer', desc: 'This person loves deals... 20% off!' },
    { icon: '✍️', name: 'Writer', job: 'Makes it personal', desc: '"Sarah, as a Gold member..."' },
    { icon: '📱', name: 'Messenger', job: 'Picks how & when', desc: 'App notification at 9am' },
  ];

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-3xl font-bold text-white mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Your AI Team (Works 24/7, Never Complains)
      </h2>

      <div className="flex gap-4">
        {team.map((member, i) => (
          <div
            key={i}
            className={`transition-all duration-500`}
            style={{
              transitionDelay: `${i * 150}ms`,
              opacity: phase >= 2 ? 1 : 0,
              transform: phase >= 2 ? 'translateY(0)' : 'translateY(20px)',
            }}
          >
            <div className={`w-36 bg-slate-800 rounded-xl p-4 text-center border border-slate-700 hover:border-blue-500/50 transition-colors ${
              i === 2 ? 'ring-2 ring-blue-500 bg-blue-900/20' : ''
            }`}>
              <div className="text-4xl mb-2">{member.icon}</div>
              <div className="text-white font-bold text-sm">{member.name}</div>
              <div className="text-blue-400 text-xs mt-1">{member.job}</div>
              <div className="text-slate-500 text-[10px] mt-2 italic">"{member.desc}"</div>
            </div>

            {i < team.length - 1 && (
              <div className="flex justify-center mt-2">
                <span className={`text-slate-600 transition-all duration-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>→</span>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className={`mt-8 bg-blue-900/20 border border-blue-500/30 rounded-xl px-6 py-3 transition-all duration-500 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        <span className="text-blue-300">💡 The Strategist is the brain - it's the only one that actually "thinks"</span>
      </div>
    </div>
  );
}

function BusinessStep4({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-12">
      {/* Customer Card */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="bg-slate-800 rounded-xl p-5 w-48">
          <div className="text-3xl mb-2">👩</div>
          <div className="text-white font-bold">Sarah Johnson</div>
          <div className="text-slate-400 text-sm">Gold Member</div>
          <div className="mt-3 space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Price Sensitive</span>
              <span className="text-amber-400">Yes</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Flies Often</span>
              <span className="text-emerald-400">Yes</span>
            </div>
          </div>
        </div>
      </div>

      {/* Thinking Process */}
      <div className={`transition-all duration-700 delay-200 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="relative">
          <div className="w-64 h-64 rounded-full bg-gradient-to-br from-blue-600/30 to-purple-600/30 flex items-center justify-center border-2 border-blue-500/30">
            <div className="text-center">
              <div className="text-6xl mb-2">🧠</div>
              <div className="text-white font-bold">Thinking...</div>
            </div>
          </div>

          {/* Thought bubbles */}
          {phase >= 3 && (
            <>
              <div className="absolute -top-4 -left-8 bg-slate-700 rounded-lg px-3 py-1 text-xs text-slate-300 animate-bounce">
                "She's price sensitive..."
              </div>
              <div className="absolute top-8 -right-12 bg-slate-700 rounded-lg px-3 py-1 text-xs text-slate-300 animate-bounce" style={{ animationDelay: '0.2s' }}>
                "Cabin is 70% full..."
              </div>
              <div className="absolute -bottom-4 left-0 bg-slate-700 rounded-lg px-3 py-1 text-xs text-slate-300 animate-bounce" style={{ animationDelay: '0.4s' }}>
                "Give her a deal!"
              </div>
            </>
          )}
        </div>
      </div>

      {/* Decision */}
      <div className={`transition-all duration-700 delay-500 ${phase >= 4 ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}>
        <div className="bg-gradient-to-br from-emerald-900/50 to-teal-900/50 rounded-xl p-5 border-2 border-emerald-500/50 w-56">
          <div className="text-emerald-400 text-sm mb-2">✅ Decision Made</div>
          <div className="text-2xl font-bold text-white">Business @ $159</div>
          <div className="text-emerald-300 text-sm mt-1">20% discount applied</div>

          <div className="mt-4 pt-4 border-t border-emerald-500/30">
            <div className="text-slate-400 text-xs">Why this works:</div>
            <div className="text-white text-sm mt-1">
              "48% will say yes at this price = more revenue than 25% at full price"
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BusinessStep5({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <div className={`text-6xl mb-4 transition-all duration-500 ${phase >= 1 ? 'scale-100' : 'scale-50'}`}>🎯</div>

      <h2 className={`text-3xl font-bold text-white mb-8 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        See It In Action
      </h2>

      <div className={`flex gap-6 mb-8 transition-all duration-700 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { pnr: 'ABC123', name: 'Sarah', result: '✅ Business @ $171', color: 'emerald' },
          { pnr: 'JKL789', name: 'David', result: '✅ Business @ $159 (20% off!)', color: 'blue' },
          { pnr: 'GHI654', name: 'Lisa', result: '❌ No offer (complaint)', color: 'red' },
        ].map((scenario, i) => (
          <div
            key={i}
            className={`bg-slate-800 rounded-xl p-4 w-52 border-2 transition-all duration-500 hover:scale-105 cursor-pointer ${
              scenario.color === 'emerald' ? 'border-emerald-500/30 hover:border-emerald-500' :
              scenario.color === 'blue' ? 'border-blue-500/30 hover:border-blue-500' :
              'border-red-500/30 hover:border-red-500'
            }`}
            style={{ transitionDelay: `${i * 150}ms` }}
          >
            <div className="text-slate-400 font-mono text-sm">{scenario.pnr}</div>
            <div className="text-white font-bold mt-1">{scenario.name}</div>
            <div className={`text-sm mt-2 ${
              scenario.color === 'emerald' ? 'text-emerald-400' :
              scenario.color === 'blue' ? 'text-blue-400' :
              'text-red-400'
            }`}>
              {scenario.result}
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
// TECHNICAL STEPS - Focus on Architecture, Code, Patterns
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
        Agentic AI Architecture
      </h1>

      <p className={`text-lg text-emerald-200 text-center max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}>
        Production-ready agent pipeline with LangGraph, conditional routing, and explainable decisions
      </p>

      <div className={`mt-10 bg-slate-900 rounded-xl p-4 font-mono text-sm transition-all duration-700 ${
        phase >= 4 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-slate-500"># Architecture Summary</div>
        <div className="text-emerald-400">pattern: <span className="text-white">Sequential + Conditional Routing</span></div>
        <div className="text-emerald-400">orchestrator: <span className="text-white">LangGraph StateGraph</span></div>
        <div className="text-emerald-400">components: <span className="text-white">4 Workflows + 1 Agent + 1 LLM</span></div>
      </div>
    </div>
  );
}

function TechStep1({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-12">
      {/* Pattern Comparison */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-slate-400 text-sm mb-4 text-center">Common Agent Patterns</h3>
        <div className="space-y-3">
          {[
            { name: 'ReAct', desc: 'Reason → Act → Observe loop', used: false },
            { name: 'Multi-Agent', desc: 'Agents talking to agents', used: false },
            { name: 'Sequential', desc: 'Pipeline with state passing', used: true },
            { name: 'LLM Router', desc: 'LLM decides next step', used: false },
          ].map((pattern, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-all duration-500 ${
                pattern.used ? 'bg-emerald-900/30 border border-emerald-500/50' : 'bg-slate-800/50'
              }`}
              style={{ transitionDelay: `${i * 100}ms`, opacity: phase >= 2 ? 1 : 0 }}
            >
              <span className={pattern.used ? 'text-emerald-400' : 'text-slate-500'}>
                {pattern.used ? '✓' : '○'}
              </span>
              <div>
                <div className={pattern.used ? 'text-emerald-300 font-medium' : 'text-slate-400'}>{pattern.name}</div>
                <div className="text-slate-500 text-xs">{pattern.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Why Sequential */}
      <div className={`max-w-md transition-all duration-700 delay-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h2 className="text-2xl font-bold text-white mb-4">Why Sequential?</h2>

        <div className="bg-slate-900 rounded-xl p-4 font-mono text-sm mb-4">
          <div className="text-slate-500"># Predictable, testable, debuggable</div>
          <div className="mt-2 text-emerald-400">
            Customer → Flight → <span className="text-blue-400">Offer</span> → Message → Channel
          </div>
          <div className="mt-2 text-slate-500"># With conditional exit points</div>
          <div className="text-amber-400">
            if not eligible: <span className="text-red-400">EXIT</span>
          </div>
        </div>

        <div className={`space-y-2 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
          {[
            { icon: '✓', text: 'Deterministic execution order' },
            { icon: '✓', text: 'Easy to test each component' },
            { icon: '✓', text: 'LLM calls only where needed' },
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-emerald-300">
              <span>{item.icon}</span>
              <span className="text-sm">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TechStep2({ phase }: { phase: number }) {
  const nodes = [
    { id: 'customer', label: 'Customer Intel', type: 'workflow', lines: 3 },
    { id: 'flight', label: 'Flight Opt', type: 'workflow', lines: 2 },
    { id: 'offer', label: 'Offer Orch', type: 'agent', lines: 15 },
    { id: 'message', label: 'Personalize', type: 'llm', lines: 1 },
    { id: 'channel', label: 'Channel', type: 'workflow', lines: 2 },
    { id: 'measure', label: 'Measure', type: 'workflow', lines: 1 },
  ];

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <h2 className={`text-xl font-bold text-white mb-6 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        4 Workflows + 1 Agent + 1 LLM Call
      </h2>

      {/* Pipeline */}
      <div className="relative mb-8">
        <svg width="720" height="80" className="absolute top-1/2 left-0 -translate-y-1/2">
          {nodes.slice(0, -1).map((_, i) => (
            <g key={i}>
              <line
                x1={60 + i * 115} y1="40" x2={100 + i * 115} y2="40"
                stroke={phase >= 2 ? '#475569' : '#1e293b'} strokeWidth="2"
              />
              {phase >= 2 && (
                <circle r="4" fill="#10b981">
                  <animateMotion dur="2s" repeatCount="indefinite" path={`M${60 + i * 115} 40 L${100 + i * 115} 40`} />
                </circle>
              )}
            </g>
          ))}
        </svg>

        <div className="flex gap-3">
          {nodes.map((node, i) => (
            <div
              key={node.id}
              className="relative z-10 transition-all duration-500"
              style={{
                transitionDelay: `${i * 100}ms`,
                opacity: phase >= 1 ? 1 : 0,
                transform: phase >= 1 ? 'translateY(0)' : 'translateY(20px)',
              }}
            >
              <div className={`w-28 h-20 rounded-xl flex flex-col items-center justify-center text-center ${
                node.type === 'agent'
                  ? 'bg-gradient-to-br from-blue-600 to-blue-700 border-2 border-blue-400 shadow-lg shadow-blue-500/30'
                  : node.type === 'llm'
                    ? 'bg-gradient-to-br from-purple-600 to-purple-700 border-2 border-purple-400'
                    : 'bg-slate-800 border border-slate-600'
              }`}>
                <div className={`text-xs font-medium ${node.type === 'workflow' ? 'text-slate-300' : 'text-white'}`}>
                  {node.label}
                </div>
                <div className={`text-[10px] mt-1 ${node.type === 'workflow' ? 'text-slate-500' : 'text-white/70'}`}>
                  {node.lines === 1 ? '~1 rule' : node.lines === 15 ? '15+ factors' : `~${node.lines} rules`}
                </div>
              </div>
              <div className={`absolute -bottom-5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-[9px] font-mono ${
                node.type === 'agent' ? 'bg-blue-500 text-white' :
                node.type === 'llm' ? 'bg-purple-500 text-white' :
                'bg-slate-700 text-slate-400'
              }`}>
                {node.type.toUpperCase()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Code snippet */}
      <div className={`bg-slate-900 rounded-xl p-4 font-mono text-xs max-w-2xl transition-all duration-700 ${
        phase >= 3 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-slate-500"># LangGraph StateGraph definition</div>
        <div className="text-emerald-400">workflow = <span className="text-white">StateGraph(OfferState)</span></div>
        <div className="text-emerald-400">workflow.add_node(<span className="text-amber-300">"customer"</span>, customer_workflow)</div>
        <div className="text-emerald-400">workflow.add_node(<span className="text-amber-300">"offer"</span>, <span className="text-blue-400">offer_agent</span>)  <span className="text-slate-500"># THE AGENT</span></div>
        <div className="text-emerald-400">workflow.add_conditional_edges(<span className="text-amber-300">"customer"</span>, should_continue)</div>
      </div>
    </div>
  );
}

function TechStep3({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* Factors Grid */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-slate-400 text-sm mb-3">15+ Factor Decision Matrix</h3>
        <div className="bg-slate-900 rounded-xl p-4 font-mono text-xs space-y-3">
          <div>
            <div className="text-slate-500 mb-1"># Customer Factors (6)</div>
            <div className="grid grid-cols-2 gap-1">
              {['loyalty_tier', 'annual_revenue', 'travel_pattern', 'acceptance_rate', 'avg_spend', 'price_sensitivity'].map((f, i) => (
                <span key={i} className={`text-emerald-400 transition-opacity duration-300`}
                  style={{ opacity: phase >= 2 ? 1 : 0, transitionDelay: `${i * 50}ms` }}>
                  {f}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="text-slate-500 mb-1"># Flight Factors (3)</div>
            <div className="flex gap-2">
              {['route', 'hours_to_dep', 'inventory_priority'].map((f, i) => (
                <span key={i} className={`text-blue-400 transition-opacity duration-300`}
                  style={{ opacity: phase >= 2 ? 1 : 0, transitionDelay: `${(i + 6) * 50}ms` }}>
                  {f}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="text-slate-500 mb-1"># Per-Offer Factors (6 × N offers)</div>
            <div className="flex gap-2 flex-wrap">
              {['p_buy', 'confidence', 'base_price', 'margin', 'max_discount', 'expected_value'].map((f, i) => (
                <span key={i} className={`text-purple-400 transition-opacity duration-300`}
                  style={{ opacity: phase >= 3 ? 1 : 0, transitionDelay: `${(i + 9) * 50}ms` }}>
                  {f}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* EV Calculation */}
      <div className={`transition-all duration-700 delay-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-slate-400 text-sm mb-3">Expected Value Optimization</h3>
        <div className="bg-slate-900 rounded-xl p-4 font-mono text-sm">
          <div className="text-slate-500 mb-2"># Core formula</div>
          <div className="text-2xl text-white mb-4">
            EV = P(buy) × Price × Margin
          </div>

          <div className="text-slate-500 mb-2"># Agent evaluates ALL price points</div>
          <div className="space-y-1">
            {[
              { price: 199, p: 0.25, ev: 44.78 },
              { price: 179, p: 0.35, ev: 56.39 },
              { price: 159, p: 0.48, ev: 68.69, best: true },
            ].map((row, i) => (
              <div key={i} className={`flex items-center gap-2 ${row.best ? 'text-emerald-400' : 'text-slate-400'}`}>
                <span>${row.price}</span>
                <span>→</span>
                <span>{row.p} × ${row.price} × 0.9</span>
                <span>=</span>
                <span className="font-bold">${row.ev.toFixed(2)}</span>
                {row.best && <span className="text-xs bg-emerald-500 text-white px-1 rounded">BEST</span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function TechStep4({ phase }: { phase: number }) {
  return (
    <div className="h-full flex items-center justify-center p-8 gap-8">
      {/* Agent vs Others */}
      <div className={`transition-all duration-700 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-slate-400 text-sm mb-3">Why Agent Here (Not Rules)</h3>
        <div className="bg-slate-900 rounded-xl p-4 space-y-3">
          {[
            { what: 'Rules Engine', why: 'Can\'t weigh 15+ factors dynamically', icon: '❌' },
            { what: 'Pure ML', why: 'Can\'t enforce business constraints', icon: '❌' },
            { what: 'LLM Every Call', why: 'Too slow, expensive, unpredictable', icon: '❌' },
            { what: 'Agent (LLM+Rules)', why: 'Reasoning + Constraints + Speed', icon: '✅' },
          ].map((row, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 transition-all duration-500`}
              style={{ transitionDelay: `${i * 150}ms`, opacity: phase >= 2 ? 1 : 0 }}
            >
              <span className="text-lg">{row.icon}</span>
              <div>
                <div className={row.icon === '✅' ? 'text-emerald-300 font-medium' : 'text-slate-400'}>{row.what}</div>
                <div className="text-slate-500 text-xs">{row.why}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* MCP Tools */}
      <div className={`transition-all duration-700 delay-300 ${phase >= 3 ? 'opacity-100' : 'opacity-0'}`}>
        <h3 className="text-slate-400 text-sm mb-3">Data via MCP Tools</h3>
        <div className="bg-slate-900 rounded-xl p-4 font-mono text-xs">
          <div className="text-slate-500 mb-2"># Standard interface to systems</div>
          <table className="w-full">
            <thead>
              <tr className="text-slate-500">
                <th className="text-left py-1">Tool</th>
                <th className="text-left py-1">Demo</th>
                <th className="text-left py-1">Prod</th>
              </tr>
            </thead>
            <tbody>
              {[
                { tool: 'get_customer()', demo: 'JSON', prod: 'Customer 360' },
                { tool: 'get_flight()', demo: 'JSON', prod: 'DCSID' },
                { tool: 'get_ml_scores()', demo: 'JSON', prod: 'ML Platform' },
              ].map((row, i) => (
                <tr key={i} className="border-t border-slate-800">
                  <td className="py-1 text-emerald-400">{row.tool}</td>
                  <td className="py-1 text-slate-400">{row.demo}</td>
                  <td className="py-1 text-blue-400">{row.prod}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 text-slate-500">
            # Swap data_tools.py → prod APIs. Zero component changes.
          </div>
        </div>
      </div>
    </div>
  );
}

function TechStep5({ phase }: { phase: number }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <div className={`font-mono text-4xl text-emerald-400 mb-4 transition-all duration-500 ${phase >= 1 ? 'scale-100' : 'scale-50'}`}>
        ./run_demo
      </div>

      <h2 className={`text-2xl font-bold text-white mb-6 transition-all duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        Explore the Architecture
      </h2>

      <div className={`grid grid-cols-3 gap-4 mb-8 transition-all duration-700 ${phase >= 2 ? 'opacity-100' : 'opacity-0'}`}>
        {[
          { file: 'agents/offer_orchestration.py', desc: 'The Agent (~200 LOC)', lines: '15+ factor EV calc' },
          { file: 'agents/workflow.py', desc: 'LangGraph Definition', lines: 'StateGraph + routing' },
          { file: 'tools/data_tools.py', desc: 'MCP Tools', lines: 'Swap for prod APIs' },
        ].map((item, i) => (
          <div
            key={i}
            className="bg-slate-800 rounded-xl p-4 border border-slate-700 hover:border-emerald-500/50 transition-colors"
            style={{ transitionDelay: `${i * 150}ms` }}
          >
            <div className="font-mono text-emerald-400 text-sm">{item.file}</div>
            <div className="text-white font-medium mt-1">{item.desc}</div>
            <div className="text-slate-500 text-xs mt-1">{item.lines}</div>
          </div>
        ))}
      </div>

      <div className={`flex items-center gap-4 bg-emerald-900/20 rounded-xl px-6 py-4 border border-emerald-500/30 transition-all duration-700 ${
        phase >= 3 ? 'opacity-100' : 'opacity-0'
      }`}>
        <div className="text-3xl">🔍</div>
        <div>
          <div className="text-white font-medium">Try different scenarios</div>
          <div className="text-emerald-300 text-sm">Watch conditional routing (GHI654 exits early)</div>
        </div>
      </div>

      <div className={`mt-4 font-mono text-xs text-slate-500 transition-all duration-500 ${phase >= 4 ? 'opacity-100' : 'opacity-0'}`}>
        💡 Check Agent Details panel for full reasoning traces
      </div>
    </div>
  );
}
