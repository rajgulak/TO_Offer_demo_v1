/**
 * GuidedDemo - Automated voice-guided tour of the 4 Pillars
 *
 * The 4 Pillars of Agentic AI:
 * 1. Planning - The Planner decides what to evaluate
 * 2. Reasoning - Worker executes, Solver decides (together = Transparency)
 * 3. Business Control - Prompt Assistant + Policy Config
 * 4. Human + AI - HITL
 *
 * Uses OpenAI TTS for natural voice.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

interface GuidedDemoProps {
  onSelectCustomer: (pnr: string) => void;
  onRunAgent: () => void;
  onToggleHITL: (enabled: boolean) => void;
  onExpandControlPanel: (expanded: boolean) => void;
  onToggleAdvancedMode: (advanced: boolean) => void;
  onOpenPromptAssistant: () => void;
  isAgentComplete: boolean;
  availablePNRs: string[];
}

interface DemoStep {
  id: string;
  narration: string;
  action?: () => void;
  waitForAgent?: boolean;
  highlight?: string;
  scrollTo?: string;
  pauseBefore?: number;
  pauseAfter?: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function GuidedDemo({
  onSelectCustomer,
  onRunAgent,
  onToggleHITL,
  onExpandControlPanel,
  onToggleAdvancedMode,
  onOpenPromptAssistant,
  isAgentComplete,
  availablePNRs,
}: GuidedDemoProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightSelector, setHighlightSelector] = useState<string | null>(null);
  const [showSubtitle, setShowSubtitle] = useState('');
  const [currentPhase, setCurrentPhase] = useState('');

  // Pre-caching state
  const [cacheProgress, setCacheProgress] = useState(0);
  const [isCaching, setIsCaching] = useState(false);
  const [cacheComplete, setCacheComplete] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCache = useRef<Map<string, string>>(new Map());
  const isPlayingRef = useRef(false);
  const isPausedRef = useRef(false);
  const waitingForAgentRef = useRef(false);
  const currentStepRef = useRef(0);
  const cachingRef = useRef(false);
  const pauseResolveRef = useRef<(() => void) | null>(null);

  // Keep refs in sync
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  useEffect(() => {
    isPausedRef.current = isPaused;
    // If resuming and there's a pending resolve, call it
    if (!isPaused && pauseResolveRef.current) {
      pauseResolveRef.current();
      pauseResolveRef.current = null;
    }
  }, [isPaused]);

  useEffect(() => {
    currentStepRef.current = currentStep;
  }, [currentStep]);

  // Scroll to element smoothly
  const scrollToElement = useCallback((selector: string): Promise<void> => {
    return new Promise((resolve) => {
      const element = document.querySelector(selector);
      if (element) {
        element.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'center'
        });
        setTimeout(resolve, 800);
      } else {
        resolve();
      }
    });
  }, []);

  // Demo steps - 4 Pillars structure
  const getDemoSteps = useCallback((): DemoStep[] => [
    // ============================================
    // INTRODUCTION - Why Agentic AI?
    // ============================================
    {
      id: 'intro-1',
      narration: "Welcome. Let me show you, what makes Agentic AI, different.",
      pauseBefore: 500,
      pauseAfter: 1500,
    },
    {
      id: 'intro-2',
      narration: "With an Agent, you give it a goal. Not step by step instructions. The agent figures out, how to reach that goal, on its own.",
      pauseAfter: 1500,
    },
    {
      id: 'intro-3',
      narration: "It plans, like a human would plan. It uses tools via MCP, when it needs data. And it reasons, like a human would reason.",
      pauseAfter: 1500,
    },
    {
      id: 'intro-4',
      narration: "We've built this, around four pillars. Let me show you, each one.",
      scrollTo: '[data-tour="pillars-grid"]',
      highlight: '[data-tour="pillars-grid"]',
      pauseBefore: 500,
      pauseAfter: 2000,
    },

    // ============================================
    // THE 4 PILLARS OVERVIEW
    // ============================================
    {
      id: 'pillars-overview',
      narration: "Here they are. Planning. Reasoning. Business Control. And, Human plus AI. Together, these give you, full transparency, into every decision.",
      highlight: '[data-tour="pillars-grid"]',
      pauseAfter: 3000,
    },

    // ============================================
    // PILLAR 1: PLANNING
    // ============================================
    {
      id: 'p1-intro',
      narration: "Pillar One. Planning. We give the agent a goal. Find the best offer, for this customer. The agent creates its own strategy, to achieve that goal.",
      pauseAfter: 1500,
    },
    {
      id: 'p1-customer',
      narration: "Let me select a customer, and show you.",
      scrollTo: '[data-tour="customer-selector"]',
      highlight: '[data-tour="customer-selector"]',
      action: () => {
        if (availablePNRs.length > 0) {
          onSelectCustomer(availablePNRs[0]);
        }
      },
      pauseBefore: 500,
      pauseAfter: 2000,
    },
    {
      id: 'p1-run',
      narration: "Watch the Planner, in action.",
      scrollTo: '[data-tour="agent-reasoning"]',
      highlight: '[data-tour="agent-reasoning"]',
      action: () => onRunAgent(),
      waitForAgent: true,
      pauseBefore: 500,
    },
    {
      id: 'p1-planner',
      narration: "See this? The Planner figured out, what factors matter, for this specific customer. Loyalty status. Recent history. Current context. Just like a human expert would.",
      scrollTo: '[data-tour="planner-section"]',
      highlight: '[data-tour="planner-section"]',
      pauseBefore: 500,
      pauseAfter: 2500,
    },
    {
      id: 'p1-summary',
      narration: "This is Pillar One. Planning. The agent decides how to solve the problem. Not us.",
      pauseAfter: 2000,
    },

    // ============================================
    // PILLAR 2: REASONING
    // ============================================
    {
      id: 'p2-intro',
      narration: "Pillar Two. Reasoning. Now the Workers execute the plan. When they need data, they use tools via MCP.",
      pauseAfter: 1500,
    },
    {
      id: 'p2-worker',
      narration: "Watch the Workers use MCP tools. Customer profile from AADV. Flight inventory from DCSID. ML scores from our models. The agent connects to existing systems, when it needs to.",
      scrollTo: '[data-tour="worker-section"]',
      highlight: '[data-tour="worker-section"]',
      pauseBefore: 500,
      pauseAfter: 2500,
    },
    {
      id: 'p2-solver',
      narration: "Then, the Solver, reasons through all the evidence. Just like a human would reason it out. And you can read, exactly how it decided.",
      scrollTo: '[data-tour="solver-section"]',
      highlight: '[data-tour="solver-section"]',
      pauseBefore: 500,
      pauseAfter: 2500,
    },
    {
      id: 'p2-transparency',
      narration: "Planning, plus Reasoning, equals Transparency. Every factor considered. Every decision explained. Full audit trail.",
      pauseAfter: 2000,
    },
    {
      id: 'p2-value',
      narration: "When a customer asks, why did I get this offer? You have a real answer. When regulators ask, how do you decide? You can show them.",
      pauseAfter: 2500,
    },

    // ============================================
    // PILLAR 3: BUSINESS CONTROL
    // ============================================
    {
      id: 'p3-intro',
      narration: "Pillar Three. Business Control. Can you actually control this AI? Absolutely.",
      pauseAfter: 1500,
    },
    {
      id: 'p3-panel',
      narration: "Let me open, the control panel.",
      scrollTo: '[data-tour="control-panel"]',
      action: () => onExpandControlPanel(true),
      pauseBefore: 500,
      pauseAfter: 1500,
    },
    {
      id: 'p3-highlight',
      narration: "This is your control center. No IT tickets. No waiting weeks. Changes take effect, immediately.",
      highlight: '[data-tour="control-panel"]',
      pauseAfter: 2000,
    },
    {
      id: 'p3-assistant',
      narration: "The Prompt Assistant, lets you give instructions, in plain English.",
      action: () => onOpenPromptAssistant(),
      pauseBefore: 500,
      pauseAfter: 2000,
    },
    {
      id: 'p3-example',
      narration: "Type, give extra discount, to customers with delays. That's it. The agent understands, and follows your instruction.",
      pauseAfter: 3000,
    },
    {
      id: 'p3-policy',
      narration: "For more direct control, there are policy values, you can adjust, in real time.",
      action: () => onToggleAdvancedMode(true),
      pauseBefore: 500,
      pauseAfter: 2000,
    },
    {
      id: 'p3-values',
      narration: "Discount percentages. VIP thresholds. Maximum amounts. Change them here. The next decision, uses them instantly.",
      highlight: '[data-tour="control-panel"]',
      pauseAfter: 2500,
    },
    {
      id: 'p3-summary',
      narration: "This is Pillar Three. Business Control. You drive the AI. Not IT. Not vendors. You.",
      action: () => {
        onToggleAdvancedMode(false);
        onExpandControlPanel(false);
      },
      pauseAfter: 2000,
    },

    // ============================================
    // PILLAR 4: HUMAN + AI
    // ============================================
    {
      id: 'p4-intro',
      narration: "Pillar Four. Human plus AI. For sensitive decisions, you might want, a human to approve.",
      pauseAfter: 1500,
    },
    {
      id: 'p4-toggle',
      narration: "That's Human in the Loop. Let me turn it on.",
      scrollTo: '[data-tour="hitl-toggle"]',
      highlight: '[data-tour="hitl-toggle"]',
      action: () => onToggleHITL(true),
      pauseBefore: 500,
      pauseAfter: 2000,
    },
    {
      id: 'p4-run',
      narration: "Now, watch what happens.",
      scrollTo: '[data-tour="agent-reasoning"]',
      action: () => onRunAgent(),
      waitForAgent: true,
      pauseBefore: 500,
    },
    {
      id: 'p4-pending',
      narration: "The agent analyzed everything, and made a recommendation. But look. It stopped. Awaiting approval.",
      scrollTo: '[data-tour="final-decision"]',
      highlight: '[data-tour="final-decision"]',
      pauseBefore: 500,
      pauseAfter: 2500,
    },
    {
      id: 'p4-approval',
      narration: "A human reviews. Then approves, or rejects. AI speed, for analysis. Human judgment, for the decision.",
      pauseAfter: 2500,
    },
    {
      id: 'p4-summary',
      narration: "This is Pillar Four. Human plus AI. Best of both worlds.",
      action: () => onToggleHITL(false),
      pauseAfter: 2000,
    },

    // ============================================
    // CLOSING
    // ============================================
    {
      id: 'close-pattern',
      narration: "One more thing. What you saw, is a pattern, you can apply anywhere.",
      pauseAfter: 1500,
    },
    {
      id: 'close-examples',
      narration: "Seat recommendations. Ancillary offers. Service routing. Loyalty decisions. Any complex decision, that needs transparency, and control.",
      pauseAfter: 2500,
    },
    {
      id: 'close-recap',
      narration: "So, why Agentic AI? Four pillars.",
      pauseAfter: 1500,
    },
    {
      id: 'close-four',
      narration: "One, Planning. The agent thinks first. Two, Reasoning. Full transparency. Three, Business control. You drive it. Four, Human plus AI. You stay in charge.",
      pauseAfter: 3000,
    },
    {
      id: 'close-end',
      narration: "That's Agentic AI. Planning. Reasoning. Control. Thank you, for watching.",
      pauseAfter: 2000,
    },
  ], [availablePNRs, onSelectCustomer, onRunAgent, onToggleHITL, onExpandControlPanel, onToggleAdvancedMode, onOpenPromptAssistant]);

  // Pre-cache a single audio file - try static first, then generate
  const cacheAudio = useCallback(async (text: string, stepId: string): Promise<boolean> => {
    if (audioCache.current.has(stepId)) return true;

    // First try to load pre-generated static audio file
    try {
      const staticResponse = await fetch(`${API_BASE}/static/audio/${stepId}.mp3`);
      if (staticResponse.ok) {
        const blob = await staticResponse.blob();
        const url = URL.createObjectURL(blob);
        audioCache.current.set(stepId, url);
        return true;
      }
    } catch {
      // Static file not available, will try generating
    }

    // Fall back to generating audio on-demand
    try {
      const response = await fetch(`${API_BASE}/api/tts/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: 'nova' }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        audioCache.current.set(stepId, url);
        return true;
      }
    } catch (error) {
      console.log(`Failed to cache audio for ${stepId}`);
    }
    return false;
  }, []);

  // Pre-cache ALL audio when panel opens
  const precacheAllAudio = useCallback(async () => {
    if (cachingRef.current || cacheComplete) return;
    cachingRef.current = true;
    setIsCaching(true);
    setCacheProgress(0);

    const steps = getDemoSteps();
    const total = steps.length;
    let completed = 0;

    // Cache in batches of 4 for faster parallel loading
    const batchSize = 4;
    for (let i = 0; i < steps.length; i += batchSize) {
      const batch = steps.slice(i, i + batchSize);
      await Promise.all(batch.map(step => cacheAudio(step.narration, step.id)));
      completed += batch.length;
      setCacheProgress(Math.min(100, Math.round((completed / total) * 100)));
    }

    setIsCaching(false);
    setCacheComplete(true);
    cachingRef.current = false;
  }, [getDemoSteps, cacheAudio, cacheComplete]);

  // Start pre-caching when panel opens
  useEffect(() => {
    if (isOpen && !cacheComplete && !cachingRef.current) {
      precacheAllAudio();
    }
  }, [isOpen, cacheComplete, precacheAllAudio]);

  // Helper to wait while paused
  const waitWhilePaused = useCallback((): Promise<void> => {
    return new Promise((resolve) => {
      if (!isPausedRef.current) {
        resolve();
      } else {
        pauseResolveRef.current = resolve;
      }
    });
  }, []);

  // Play narration (audio should already be cached)
  const playNarration = useCallback(async (text: string, stepId: string): Promise<void> => {
    return new Promise(async (resolve) => {
      setShowSubtitle(text);

      // Wait if paused before starting
      if (isPausedRef.current) {
        await waitWhilePaused();
      }

      if (audioCache.current.has(stepId)) {
        const cachedUrl = audioCache.current.get(stepId)!;
        if (audioRef.current) {
          audioRef.current.src = cachedUrl;
          audioRef.current.onended = () => resolve();
          audioRef.current.onerror = () => resolve();
          try {
            await audioRef.current.play();
            return;
          } catch {
            // Fall through to fallback
          }
        }
      }

      // Fallback: estimate reading time
      const words = text.split(' ').length;
      const readingTime = Math.max(3000, words * 300);
      setTimeout(resolve, readingTime);
    });
  }, [waitWhilePaused]);

  // Process a single step
  const processStep = useCallback(async (stepIndex: number) => {
    const steps = getDemoSteps();

    if (stepIndex >= steps.length || !isPlayingRef.current) {
      setIsPlaying(false);
      setCurrentStep(0);
      setHighlightSelector(null);
      setShowSubtitle('');
      setCurrentPhase('');
      waitingForAgentRef.current = false;
      return;
    }

    const step = steps[stepIndex];
    setCurrentStep(stepIndex);
    currentStepRef.current = stepIndex;

    // Update phase indicator
    if (step.id.startsWith('intro')) setCurrentPhase('Introduction');
    else if (step.id.startsWith('pillars')) setCurrentPhase('The 4 Pillars');
    else if (step.id.startsWith('p1')) setCurrentPhase('Pillar 1: Planning');
    else if (step.id.startsWith('p2')) setCurrentPhase('Pillar 2: Reasoning');
    else if (step.id.startsWith('p3')) setCurrentPhase('Pillar 3: Business Control');
    else if (step.id.startsWith('p4')) setCurrentPhase('Pillar 4: Human + AI');
    else if (step.id.startsWith('close')) setCurrentPhase('Summary');

    // 1. Pause before
    if (step.pauseBefore) {
      await new Promise(r => setTimeout(r, step.pauseBefore));
    }
    if (!isPlayingRef.current) return;

    // 2. Scroll to element
    if (step.scrollTo) {
      await scrollToElement(step.scrollTo);
    }
    if (!isPlayingRef.current) return;

    // 3. Highlight element
    setHighlightSelector(step.highlight || null);
    if (step.highlight) {
      await new Promise(r => setTimeout(r, 500));
    }
    if (!isPlayingRef.current) return;

    // 4. Execute action
    if (step.action) {
      step.action();
      await new Promise(r => setTimeout(r, 500));
    }
    if (!isPlayingRef.current) return;

    // 5. If waiting for agent, set flag and return
    if (step.waitForAgent) {
      waitingForAgentRef.current = true;
      await playNarration(step.narration, step.id);
      return;
    }

    // 6. Play narration
    await playNarration(step.narration, step.id);
    if (!isPlayingRef.current) return;

    // 7. Pause after
    if (step.pauseAfter) {
      await new Promise(r => setTimeout(r, step.pauseAfter));
    }
    if (!isPlayingRef.current) return;

    // 8. Clear and continue
    setShowSubtitle('');
    processStep(stepIndex + 1);
  }, [getDemoSteps, playNarration, scrollToElement]);

  // Watch for agent completion
  useEffect(() => {
    if (waitingForAgentRef.current && isAgentComplete && isPlayingRef.current) {
      waitingForAgentRef.current = false;
      setTimeout(() => {
        setShowSubtitle('');
        processStep(currentStepRef.current + 1);
      }, 2000);
    }
  }, [isAgentComplete, processStep]);

  // Start demo
  const startDemo = useCallback(() => {
    setIsPlaying(true);
    isPlayingRef.current = true;
    setCurrentStep(0);
    currentStepRef.current = 0;
    waitingForAgentRef.current = false;
    setCurrentPhase('');
    processStep(0);
  }, [processStep]);

  // Stop demo
  const stopDemo = useCallback(() => {
    setIsPlaying(false);
    isPlayingRef.current = false;
    setIsPaused(false);
    isPausedRef.current = false;
    setCurrentStep(0);
    setHighlightSelector(null);
    setShowSubtitle('');
    setCurrentPhase('');
    waitingForAgentRef.current = false;
    if (audioRef.current) {
      audioRef.current.pause();
    }
    onToggleHITL(false);
    onExpandControlPanel(false);
    onToggleAdvancedMode(false);
  }, [onToggleHITL, onExpandControlPanel, onToggleAdvancedMode]);

  // Pause demo
  const pauseDemo = useCallback(() => {
    setIsPaused(true);
    isPausedRef.current = true;
    if (audioRef.current) {
      audioRef.current.pause();
    }
  }, []);

  // Resume demo
  const resumeDemo = useCallback(() => {
    setIsPaused(false);
    isPausedRef.current = false;
    if (audioRef.current && audioRef.current.src && !audioRef.current.ended) {
      audioRef.current.play().catch(() => {});
    }
  }, []);

  const demoSteps = getDemoSteps();
  const progress = ((currentStep + 1) / demoSteps.length) * 100;

  return (
    <>
      <audio ref={audioRef} />

      {/* Highlight Overlay */}
      {highlightSelector && isPlaying && (
        <div className="fixed inset-0 z-40 pointer-events-none">
          <div className="absolute inset-0 bg-black/60 transition-opacity duration-500" />
          <style>{`
            ${highlightSelector} {
              position: relative;
              z-index: 50 !important;
              box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.9), 0 0 40px rgba(34, 211, 238, 0.5), 0 0 80px rgba(34, 211, 238, 0.3) !important;
              border-radius: 12px;
              transition: box-shadow 0.3s ease;
            }
          `}</style>
        </div>
      )}

      {/* Phase Indicator - Top of screen */}
      {currentPhase && isPlaying && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50">
          <div className={`text-white px-6 py-2 rounded-full shadow-lg flex items-center gap-2 ${
            isPaused
              ? 'bg-gradient-to-r from-amber-600 to-orange-600'
              : 'bg-gradient-to-r from-purple-600 to-indigo-600'
          }`}>
            {isPaused && <span>⏸️</span>}
            <span className="font-semibold">{currentPhase}</span>
            {isPaused && <span className="text-sm opacity-80">- Paused</span>}
          </div>
        </div>
      )}

      {/* Floating Button */}
      <div className="fixed bottom-6 left-24 z-50">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-110 ${
            isPaused
              ? 'bg-gradient-to-r from-amber-500 to-orange-500'
              : isPlaying
                ? 'bg-gradient-to-r from-cyan-500 to-purple-500 animate-pulse'
                : 'bg-gradient-to-r from-emerald-600 to-cyan-600'
          }`}
          title="Guided Demo"
        >
          <span className="text-2xl">{isPaused ? '⏸️' : isPlaying ? '🎙️' : '🎬'}</span>
        </button>
      </div>

      {/* Control Panel */}
      {isOpen && (
        <div className="fixed bottom-24 left-24 z-50 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-2xl shadow-2xl w-96 overflow-hidden">
          <div className="bg-gradient-to-r from-emerald-600 to-cyan-600 px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎬</span>
                <span className="font-bold text-white">Guided Demo</span>
              </div>
              <button onClick={() => setIsOpen(false)} className="text-white/70 hover:text-white">
                ✕
              </button>
            </div>
            <p className="text-xs text-white/70 mt-1">Voice-guided tour of the 4 Pillars</p>
          </div>

          <div className="p-4 space-y-4">
            {isPlaying ? (
              <>
                {/* Progress */}
                <div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                    <span>{currentPhase || 'Starting...'}</span>
                    <span>{currentStep + 1} / {demoSteps.length}</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div
                      className="bg-gradient-to-r from-emerald-500 to-cyan-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>

                {/* Current Step */}
                <div className={`rounded-lg p-3 ${isPaused ? 'bg-amber-900/30 border border-amber-500/50' : 'bg-slate-800/50'}`}>
                  <div className={`text-xs mb-1 ${isPaused ? 'text-amber-400' : 'text-cyan-400'}`}>
                    {isPaused ? '⏸️ Paused' : 'Now Playing'}
                  </div>
                  <div className="text-sm text-white line-clamp-3">
                    {showSubtitle || 'Preparing...'}
                  </div>
                </div>

                {/* Pause/Resume and Stop Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={isPaused ? resumeDemo : pauseDemo}
                    className={`flex-1 py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${
                      isPaused
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                        : 'bg-amber-600 hover:bg-amber-500 text-white'
                    }`}
                  >
                    <span>{isPaused ? '▶️' : '⏸️'}</span> {isPaused ? 'Resume' : 'Pause'}
                  </button>
                  <button
                    onClick={stopDemo}
                    className="flex-1 py-3 rounded-xl font-medium bg-red-600 hover:bg-red-500 text-white flex items-center justify-center gap-2"
                  >
                    <span>⏹️</span> Stop
                  </button>
                </div>
              </>
            ) : (
              <>
                {/* Caching Progress */}
                {isCaching && (
                  <div className="bg-slate-800/50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-white">Preparing audio...</span>
                      <span className="text-xs text-cyan-400">{cacheProgress}%</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-cyan-500 to-emerald-500 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${cacheProgress}%` }}
                      />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">Pre-loading voice narration...</p>
                  </div>
                )}

                {/* Ready State */}
                {cacheComplete && (
                  <div className="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-emerald-400">
                      <span>✓</span>
                      <span className="text-sm font-medium">Audio ready!</span>
                    </div>
                  </div>
                )}

                {/* Description */}
                <div className="text-sm text-slate-300 space-y-2">
                  <p>This tour explains the 4 Pillars:</p>
                  <ul className="text-xs text-slate-400 space-y-1 ml-4">
                    <li>• Planning - Agent thinks first</li>
                    <li>• Reasoning - Full transparency</li>
                    <li>• Business Control - You drive it</li>
                    <li>• Human + AI - You stay in charge</li>
                  </ul>
                </div>

                {/* Start Button */}
                <button
                  onClick={startDemo}
                  disabled={isCaching}
                  className={`w-full py-4 rounded-xl font-medium text-white flex items-center justify-center gap-2 text-lg transition-all ${
                    isCaching
                      ? 'bg-slate-600 cursor-not-allowed'
                      : 'bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500'
                  }`}
                >
                  {isCaching ? (
                    <>
                      <span className="animate-spin">⏳</span> Preparing...
                    </>
                  ) : (
                    <>
                      <span>▶️</span> Start Guided Demo
                    </>
                  )}
                </button>

                <div className="text-xs text-slate-500 text-center">
                  ~4 minutes • Voice narration • Auto-scrolling
                </div>
              </>
            )}
          </div>

          {/* 4 Pillars Preview */}
          {!isPlaying && (
            <div className="border-t border-slate-700 px-4 py-3">
              <div className="text-xs text-slate-400 mb-2">The 4 Pillars</div>
              <div className="grid grid-cols-4 gap-2 text-center">
                {[
                  { icon: '📋', label: 'Planning' },
                  { icon: '🧠', label: 'Reasoning' },
                  { icon: '🎛️', label: 'Control' },
                  { icon: '🤝', label: 'Human+AI' },
                ].map((pillar, i) => (
                  <div key={i} className="flex flex-col items-center">
                    <span className="text-lg">{pillar.icon}</span>
                    <span className="text-[10px] text-slate-500 mt-1">{pillar.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
