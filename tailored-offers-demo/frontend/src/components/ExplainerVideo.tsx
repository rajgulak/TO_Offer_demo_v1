/**
 * ExplainerVideo - Animated explainer for the AI Agent demo
 *
 * A cinematic introduction that explains:
 * 1. What AI Agents are
 * 2. How they differ from traditional automation
 * 3. The ReWOO pattern
 * 4. Demo walkthrough
 *
 * Features natural voice narration via OpenAI TTS
 */
import { useState, useEffect, useCallback, useRef } from 'react';

// Scene definitions
interface Scene {
  id: string;
  duration: number; // in seconds
  title?: string;
  content: React.ReactNode;
}

// Individual scene components
function TitleScene() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="animate-fadeInUp">
        <div className="text-6xl mb-6">🤖</div>
        <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          AI Agents
        </h1>
        <p className="text-xl text-slate-300 mb-8">
          The Future of Intelligent Automation
        </p>
        <div className="flex items-center justify-center gap-2 text-slate-400">
          <span className="w-12 h-px bg-slate-600"></span>
          <span className="text-sm">American Airlines</span>
          <span className="w-12 h-px bg-slate-600"></span>
        </div>
      </div>
    </div>
  );
}

function TraditionalAutomationScene() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setStep(s => (s + 1) % 4);
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-3xl font-bold mb-8 text-slate-200 animate-fadeInUp">
        Traditional Automation
      </h2>

      <div className="flex items-center gap-4 mb-8">
        {['If A', 'Then B', 'Else C', 'End'].map((label, idx) => (
          <div key={idx} className="flex items-center">
            <div
              className={`w-24 h-16 rounded-lg flex items-center justify-center text-sm font-mono transition-all duration-500 ${
                step === idx
                  ? 'bg-amber-500 text-black scale-110 shadow-lg shadow-amber-500/50'
                  : 'bg-slate-700 text-slate-300'
              }`}
            >
              {label}
            </div>
            {idx < 3 && (
              <div className={`w-8 h-0.5 transition-colors duration-500 ${
                step > idx ? 'bg-amber-500' : 'bg-slate-600'
              }`}></div>
            )}
          </div>
        ))}
      </div>

      <div className="max-w-lg text-center animate-fadeInUp animation-delay-500">
        <p className="text-slate-400 text-lg">
          <span className="text-amber-400 font-semibold">Rigid rules.</span> Fixed paths.
          <br />
          Every scenario must be pre-programmed.
        </p>
      </div>

      <div className="mt-8 flex gap-4">
        {['❌ Limited flexibility', '❌ Maintenance nightmare', '❌ Cannot adapt'].map((text, idx) => (
          <div
            key={idx}
            className="bg-red-900/30 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-300 animate-fadeInUp"
            style={{ animationDelay: `${idx * 200}ms` }}
          >
            {text}
          </div>
        ))}
      </div>
    </div>
  );
}

function AgentIntroScene() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-3xl font-bold mb-8 text-slate-200 animate-fadeInUp">
        Enter: <span className="text-cyan-400">AI Agents</span>
      </h2>

      <div className="relative mb-8">
        <div className="w-32 h-32 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center animate-pulse-slow">
          <span className="text-6xl">🧠</span>
        </div>
        <div className="absolute -top-2 -right-2 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center animate-bounce">
          <span className="text-lg">✨</span>
        </div>
      </div>

      <div className="max-w-2xl text-center mb-8 animate-fadeInUp animation-delay-300">
        <p className="text-xl text-slate-300">
          Agents are <span className="text-cyan-400 font-semibold">autonomous systems</span> that
          can <span className="text-emerald-400 font-semibold">reason</span>,
          <span className="text-purple-400 font-semibold"> plan</span>, and
          <span className="text-amber-400 font-semibold"> act</span> to achieve goals.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6 animate-fadeInUp animation-delay-500">
        {[
          { icon: '🎯', title: 'Goal-Oriented', desc: 'Give it objectives, not instructions' },
          { icon: '🔄', title: 'Adaptive', desc: 'Handles new situations gracefully' },
          { icon: '💡', title: 'Explainable', desc: 'Shows its reasoning process' },
        ].map((item, idx) => (
          <div key={idx} className="bg-slate-800/50 border border-cyan-500/30 rounded-xl p-4 text-center">
            <div className="text-3xl mb-2">{item.icon}</div>
            <div className="font-semibold text-cyan-300 mb-1">{item.title}</div>
            <div className="text-sm text-slate-400">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComparisonScene() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-3xl font-bold mb-8 text-slate-200 animate-fadeInUp">
        The Difference
      </h2>

      <div className="grid grid-cols-2 gap-8 max-w-4xl">
        {/* Traditional */}
        <div className="bg-slate-800/50 border border-red-500/30 rounded-2xl p-6 animate-fadeInLeft">
          <div className="text-center mb-4">
            <span className="text-4xl">⚙️</span>
            <h3 className="text-xl font-bold text-red-400 mt-2">Traditional Workflow</h3>
          </div>
          <ul className="space-y-3 text-slate-300">
            <li className="flex items-start gap-2">
              <span className="text-red-400">→</span>
              <span>Pre-defined decision trees</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-400">→</span>
              <span>Developers write every rule</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-400">→</span>
              <span>Fails on edge cases</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-400">→</span>
              <span>Updates require code changes</span>
            </li>
          </ul>
          <div className="mt-4 text-center text-sm text-red-300 bg-red-900/20 rounded-lg py-2">
            "Computer, do exactly this..."
          </div>
        </div>

        {/* Agent */}
        <div className="bg-slate-800/50 border border-cyan-500/30 rounded-2xl p-6 animate-fadeInRight">
          <div className="text-center mb-4">
            <span className="text-4xl">🤖</span>
            <h3 className="text-xl font-bold text-cyan-400 mt-2">AI Agent</h3>
          </div>
          <ul className="space-y-3 text-slate-300">
            <li className="flex items-start gap-2">
              <span className="text-cyan-400">→</span>
              <span>Reasons about each situation</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyan-400">→</span>
              <span>Business users define goals</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyan-400">→</span>
              <span>Adapts to new scenarios</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-cyan-400">→</span>
              <span>Edit prompts in plain English</span>
            </li>
          </ul>
          <div className="mt-4 text-center text-sm text-cyan-300 bg-cyan-900/20 rounded-lg py-2">
            "Agent, achieve this goal..."
          </div>
        </div>
      </div>
    </div>
  );
}

function ReWOOScene() {
  const [activePhase, setActivePhase] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActivePhase(p => (p + 1) % 4);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  const phases = [
    { icon: '📋', name: 'Planner', color: 'cyan', desc: 'Analyzes data & creates evaluation plan' },
    { icon: '⚙️', name: 'Worker', color: 'purple', desc: 'Executes all evaluations in parallel' },
    { icon: '✅', name: 'Solver', color: 'emerald', desc: 'Synthesizes evidence & decides' },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-3xl font-bold mb-2 text-slate-200 animate-fadeInUp">
        The <span className="text-cyan-400">ReWOO</span> Pattern
      </h2>
      <p className="text-slate-400 mb-8 animate-fadeInUp animation-delay-200">
        Reasoning Without Observation - Efficient & Transparent
      </p>

      <div className="flex items-center gap-4 mb-8">
        {phases.map((phase, idx) => (
          <div key={idx} className="flex items-center">
            <div
              className={`w-40 rounded-2xl p-4 text-center transition-all duration-500 ${
                activePhase === idx
                  ? phase.color === 'cyan' ? 'bg-cyan-600 scale-110 shadow-lg shadow-cyan-500/50' :
                    phase.color === 'purple' ? 'bg-purple-600 scale-110 shadow-lg shadow-purple-500/50' :
                    'bg-emerald-600 scale-110 shadow-lg shadow-emerald-500/50'
                  : 'bg-slate-700'
              }`}
            >
              <div className="text-3xl mb-2">{phase.icon}</div>
              <div className="font-bold text-white">{phase.name}</div>
              <div className={`text-xs mt-1 ${activePhase === idx ? 'text-white/80' : 'text-slate-400'}`}>
                {phase.desc}
              </div>
            </div>
            {idx < 2 && (
              <div className={`w-8 h-1 mx-2 rounded transition-colors duration-500 ${
                activePhase > idx
                  ? phase.color === 'cyan' ? 'bg-cyan-500' : 'bg-purple-500'
                  : 'bg-slate-600'
              }`}></div>
            )}
          </div>
        ))}
      </div>

      <div className="bg-slate-800/50 border border-slate-600 rounded-xl p-4 max-w-xl text-center animate-fadeInUp animation-delay-500">
        <p className="text-slate-300">
          Only <span className="text-cyan-400 font-bold">2-3 LLM calls</span> total,
          compared to <span className="text-red-400">N calls</span> in older patterns.
          <br />
          <span className="text-slate-400 text-sm">Fast, efficient, and fully transparent!</span>
        </p>
      </div>
    </div>
  );
}

function DemoWalkthroughScene() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h2 className="text-3xl font-bold mb-8 text-slate-200 animate-fadeInUp">
        Demo Walkthrough
      </h2>

      <div className="grid grid-cols-2 gap-6 max-w-4xl">
        {[
          { step: '1', icon: '🎛️', title: 'Control Agent', desc: 'Edit Planner, Worker, Solver prompts in plain English', color: 'cyan' },
          { step: '2', icon: '👤', title: 'Select Customer', desc: 'Choose a PNR to see different scenarios', color: 'blue' },
          { step: '3', icon: '▶️', title: 'Run Agent', desc: 'Watch real-time reasoning from LangGraph', color: 'emerald' },
          { step: '4', icon: '🎯', title: 'See Decision', desc: 'Agent recommends personalized offer', color: 'amber' },
        ].map((item, idx) => (
          <div
            key={idx}
            className={`bg-slate-800/50 border rounded-xl p-4 flex items-start gap-4 animate-fadeInUp ${
              item.color === 'cyan' ? 'border-cyan-500/30' :
              item.color === 'blue' ? 'border-blue-500/30' :
              item.color === 'emerald' ? 'border-emerald-500/30' :
              'border-amber-500/30'
            }`}
            style={{ animationDelay: `${idx * 150}ms` }}
          >
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold ${
              item.color === 'cyan' ? 'bg-cyan-600' :
              item.color === 'blue' ? 'bg-blue-600' :
              item.color === 'emerald' ? 'bg-emerald-600' :
              'bg-amber-600'
            }`}>
              {item.step}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{item.icon}</span>
                <span className="font-semibold text-white">{item.title}</span>
              </div>
              <p className="text-sm text-slate-400">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 text-center animate-fadeInUp animation-delay-700">
        <p className="text-slate-400">
          Try editing prompts to see how agent behavior changes!
        </p>
      </div>
    </div>
  );
}

function OutroScene() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="animate-fadeInUp">
        <div className="text-6xl mb-6">🚀</div>
        <h2 className="text-4xl font-bold mb-4 text-white">
          Ready to Explore?
        </h2>
        <p className="text-xl text-slate-300 mb-8">
          Click anywhere to close and start the demo
        </p>
        <div className="flex items-center justify-center gap-4">
          <div className="bg-cyan-600 rounded-full px-6 py-3 text-white font-semibold animate-pulse">
            Let's Go!
          </div>
        </div>
      </div>
    </div>
  );
}

// Voice options for TTS
const VOICE_OPTIONS = [
  { id: 'nova', label: 'Nova', description: 'Warm, engaging' },
  { id: 'alloy', label: 'Alloy', description: 'Neutral, balanced' },
  { id: 'echo', label: 'Echo', description: 'Deeper tone' },
  { id: 'fable', label: 'Fable', description: 'Expressive' },
  { id: 'onyx', label: 'Onyx', description: 'Deep, resonant' },
  { id: 'shimmer', label: 'Shimmer', description: 'Clear, optimistic' },
];

// Narration text for subtitles (fallback when audio unavailable)
const SCENE_NARRATIONS: Record<string, string> = {
  'title': 'Welcome to AI Agents. The future of intelligent automation for American Airlines.',
  'traditional': 'Traditional automation relies on rigid if-then-else rules. Every scenario must be pre-programmed. When edge cases appear, the system fails. Updates require code changes and lengthy deployment cycles.',
  'agent-intro': 'AI Agents are autonomous systems that can reason, plan, and act to achieve goals. They are goal-oriented, adaptive, and explainable.',
  'comparison': 'Traditional workflows use pre-defined decision trees. AI Agents reason about each situation dynamically. Business users define goals in plain English.',
  'rewoo': 'This demo uses the ReWOO pattern: Planner analyzes data, Worker executes evaluations in parallel, Solver synthesizes evidence and decides. Only 2-3 LLM calls total.',
  'walkthrough': 'Use the prompt editor to control agent behavior. Select a customer scenario. Click Run Agent to watch real-time reasoning. See the personalized offer recommendation.',
  'outro': 'You are ready to explore AI Agents. Click anywhere to close and start the demo.',
};

// Main component
export function ExplainerVideo() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentScene, setCurrentScene] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isAudioLoading, setIsAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState('nova');
  const [showVoiceSelector, setShowVoiceSelector] = useState(false);
  const [showSubtitles, setShowSubtitles] = useState(true); // Show subtitles by default
  const [audioUnavailable, setAudioUnavailable] = useState(false); // TTS not available
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCache = useRef<Map<string, string>>(new Map());
  const currentlyPlayingScene = useRef<string | null>(null);
  const isPlayingRef = useRef(false);

  const scenes: Scene[] = [
    { id: 'title', duration: 8, content: <TitleScene /> },
    { id: 'traditional', duration: 25, title: 'Traditional Automation', content: <TraditionalAutomationScene /> },
    { id: 'agent-intro', duration: 22, title: 'AI Agents', content: <AgentIntroScene /> },
    { id: 'comparison', duration: 28, title: 'The Difference', content: <ComparisonScene /> },
    { id: 'rewoo', duration: 30, title: 'ReWOO Pattern', content: <ReWOOScene /> },
    { id: 'walkthrough', duration: 25, title: 'Demo Walkthrough', content: <DemoWalkthroughScene /> },
    { id: 'outro', duration: 12, content: <OutroScene /> },
  ];

  // Keep ref in sync with state
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // Play audio when scene changes
  useEffect(() => {
    if (!isOpen || !isPlaying || isMuted) return;

    const sceneId = scenes[currentScene].id;
    const cacheKey = `${sceneId}-${selectedVoice}`;

    // Prevent duplicate plays for the same scene
    if (currentlyPlayingScene.current === cacheKey) {
      return;
    }

    // Stop current audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    currentlyPlayingScene.current = cacheKey;
    setIsAudioLoading(true);
    setAudioError(null);

    const playAudio = async () => {
      try {
        // Check cache first
        let audioUrl = audioCache.current.get(cacheKey);

        if (!audioUrl) {
          // Try static audio file first (works offline)
          try {
            const staticResponse = await fetch(`/audio/${sceneId}.mp3`);
            if (staticResponse.ok) {
              const blob = await staticResponse.blob();
              audioUrl = URL.createObjectURL(blob);
              audioCache.current.set(cacheKey, audioUrl);
            }
          } catch {
            // Static file not available, will try API
          }

          // If no static file, try TTS API
          if (!audioUrl) {
            const response = await fetch(`/api/tts/narration/${sceneId}?voice=${selectedVoice}`);

            if (!response.ok) {
              const error = await response.json();
              throw new Error(error.detail || 'Failed to load audio');
            }

            const blob = await response.blob();
            audioUrl = URL.createObjectURL(blob);
            audioCache.current.set(cacheKey, audioUrl);
          }
        }

        // Create and play audio
        const audio = new Audio(audioUrl);
        audioRef.current = audio;

        audio.onended = () => {
          currentlyPlayingScene.current = null;
          // Auto-advance when audio finishes (if still playing)
          if (isPlayingRef.current) {
            setCurrentScene(s => {
              if (s < scenes.length - 1) {
                return s + 1;
              } else {
                setIsPlaying(false);
                return s;
              }
            });
          }
        };

        audio.onerror = () => {
          currentlyPlayingScene.current = null;
          setAudioError('Audio playback failed');
        };

        await audio.play();
        setIsAudioLoading(false);
        setAudioUnavailable(false);

      } catch (error) {
        currentlyPlayingScene.current = null;
        setIsAudioLoading(false);
        setAudioUnavailable(true);
        setShowSubtitles(true); // Force subtitles when audio unavailable

        const errorMsg = error instanceof Error ? error.message : 'Audio failed';
        // Only show error on first failure, not for every scene
        if (!audioError) {
          setAudioError(errorMsg.includes('API key') ? 'Voice unavailable - showing subtitles' : errorMsg);
        }
        console.log('Audio unavailable, using subtitles:', errorMsg);

        // Fall back to timer-based advancement
        const sceneDuration = scenes[currentScene].duration;
        setTimeout(() => {
          if (isPlayingRef.current && currentScene < scenes.length - 1) {
            setCurrentScene(s => s + 1);
          }
        }, sceneDuration * 1000);
      }
    };

    playAudio();
  }, [currentScene, isOpen, isPlaying, isMuted, selectedVoice, scenes]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      // Revoke cached blob URLs
      audioCache.current.forEach(url => URL.revokeObjectURL(url));
    };
  }, []);

  const handleOpen = useCallback(() => {
    currentlyPlayingScene.current = null; // Reset tracking
    setCurrentScene(0);
    setIsOpen(true);
    setIsPlaying(true);
    setAudioError(null);
  }, []);

  const handleClose = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    currentlyPlayingScene.current = null;
    setIsOpen(false);
    setIsPlaying(false);
    setCurrentScene(0);
  }, []);

  const handlePrevious = useCallback(() => {
    if (currentScene > 0) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setCurrentScene(s => s - 1);
    }
  }, [currentScene]);

  const handleNext = useCallback(() => {
    if (currentScene < scenes.length - 1) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setCurrentScene(s => s + 1);
    }
  }, [currentScene, scenes.length]);

  const togglePlayPause = useCallback(() => {
    if (isPlaying) {
      // Pause
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setIsPlaying(false);
    } else {
      // Resume
      setIsPlaying(true);
      if (audioRef.current && !isMuted) {
        audioRef.current.play().catch(() => {});
      }
    }
  }, [isPlaying, isMuted]);

  const toggleMute = useCallback(() => {
    setIsMuted(m => {
      const newMuted = !m;
      if (newMuted) {
        // Muting - pause audio
        if (audioRef.current) {
          audioRef.current.pause();
        }
      } else {
        // Unmuting - reset tracking so audio can play
        currentlyPlayingScene.current = null;
      }
      return newMuted;
    });
  }, []);

  // Calculate progress
  const progress = ((currentScene + 1) / scenes.length) * 100;

  return (
    <>
      {/* Trigger Button - Fixed position */}
      <button
        onClick={handleOpen}
        className="fixed bottom-6 right-6 z-40 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-full px-6 py-3 shadow-2xl flex items-center gap-3 transition-all hover:scale-105 group"
      >
        <span className="text-2xl group-hover:animate-bounce">🎬</span>
        <span className="font-semibold">Watch Explainer</span>
        <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">2 min</span>
      </button>

      {/* Video Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center"
          onClick={(e) => {
            if (e.target === e.currentTarget && currentScene === scenes.length - 1) {
              handleClose();
            }
          }}
        >
          {/* Video Container */}
          <div className="relative w-full max-w-5xl h-[80vh] bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl overflow-hidden shadow-2xl border border-slate-700">
            {/* Close Button */}
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 z-10 w-10 h-10 bg-slate-800/80 hover:bg-slate-700 rounded-full flex items-center justify-center text-slate-300 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Scene Content */}
            <div className="h-full p-8 flex items-center justify-center">
              <div key={currentScene} className="w-full h-full animate-fadeIn">
                {scenes[currentScene].content}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-700">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>

            {/* Audio Status */}
            {isAudioLoading && (
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-slate-800/80 rounded-lg px-3 py-2">
                <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-xs text-slate-300">Loading voice...</span>
              </div>
            )}

            {audioError && !isMuted && (
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-slate-800/90 rounded-lg px-3 py-2">
                <span className="text-cyan-400">💬</span>
                <span className="text-xs text-slate-300">Subtitles enabled</span>
              </div>
            )}

            {/* Subtitles */}
            {showSubtitles && (
              <div className="absolute bottom-24 left-1/2 -translate-x-1/2 max-w-3xl w-full px-4">
                <div className="bg-black/80 rounded-lg px-6 py-3 text-center">
                  <p className="text-white text-lg leading-relaxed">
                    {SCENE_NARRATIONS[scenes[currentScene].id] || ''}
                  </p>
                </div>
              </div>
            )}

            {/* Voice Selector */}
            {showVoiceSelector && (
              <div className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-slate-800 rounded-xl p-4 shadow-xl border border-slate-600">
                <div className="text-sm text-slate-300 mb-3 font-medium">Select Voice</div>
                <div className="grid grid-cols-3 gap-2">
                  {VOICE_OPTIONS.map(voice => (
                    <button
                      key={voice.id}
                      onClick={() => {
                        if (audioRef.current) {
                          audioRef.current.pause();
                        }
                        setSelectedVoice(voice.id);
                        setShowVoiceSelector(false);
                        // Reset tracking so new voice plays
                        currentlyPlayingScene.current = null;
                      }}
                      className={`px-3 py-2 rounded-lg text-sm transition-all ${
                        selectedVoice === voice.id
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      <div className="font-medium">{voice.label}</div>
                      <div className="text-xs opacity-70">{voice.description}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-3 bg-slate-800/90 rounded-full px-4 py-2">
              {/* Mute/Unmute */}
              <button
                onClick={toggleMute}
                className={`w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
                  isMuted ? 'text-red-400 hover:text-red-300' : 'text-slate-300 hover:text-white'
                }`}
                title={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted ? (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  </svg>
                )}
              </button>

              {/* Subtitles toggle */}
              <button
                onClick={() => setShowSubtitles(s => !s)}
                className={`w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
                  showSubtitles ? 'text-cyan-400 hover:text-cyan-300' : 'text-slate-300 hover:text-white'
                }`}
                title={showSubtitles ? 'Hide subtitles' : 'Show subtitles'}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
              </button>

              {/* Voice selector button */}
              <button
                onClick={() => setShowVoiceSelector(s => !s)}
                disabled={audioUnavailable}
                className={`w-8 h-8 flex items-center justify-center transition-colors ${
                  audioUnavailable
                    ? 'text-slate-500 cursor-not-allowed'
                    : 'text-slate-300 hover:text-white'
                }`}
                title={audioUnavailable ? 'Voice unavailable' : 'Change voice'}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              </button>

              <div className="w-px h-6 bg-slate-600"></div>

              {/* Previous */}
              <button
                onClick={handlePrevious}
                disabled={currentScene === 0}
                className="w-8 h-8 flex items-center justify-center text-slate-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              {/* Play/Pause */}
              <button
                onClick={togglePlayPause}
                className="w-10 h-10 bg-cyan-600 hover:bg-cyan-500 rounded-full flex items-center justify-center text-white transition-colors"
              >
                {isPlaying ? (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>

              {/* Next */}
              <button
                onClick={handleNext}
                disabled={currentScene === scenes.length - 1}
                className="w-8 h-8 flex items-center justify-center text-slate-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              <div className="w-px h-6 bg-slate-600"></div>

              {/* Scene indicator */}
              <div className="flex items-center gap-1">
                {scenes.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.pause();
                      }
                      setCurrentScene(idx);
                    }}
                    className={`w-2 h-2 rounded-full transition-all ${
                      idx === currentScene ? 'bg-cyan-400 w-4' : 'bg-slate-600 hover:bg-slate-500'
                    }`}
                  />
                ))}
              </div>

              {/* Time */}
              <div className="text-xs text-slate-400 ml-1">
                {currentScene + 1} / {scenes.length}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
