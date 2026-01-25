/**
 * FloatingRobot - An interactive AI assistant for the demo
 *
 * Features:
 * - Floating animated robot character
 * - Voice input (speech recognition)
 * - Voice output (text-to-speech)
 * - Knowledge about the demo, agents, and ReWOO pattern
 * - Can give tutorials and answer questions
 */
import { useState, useEffect, useRef, useCallback } from 'react';

// Knowledge base about the demo
const KNOWLEDGE_BASE = {
  greeting: [
    "Hello! I'm your AI demo assistant. I'm here to help you understand how intelligent agents make decisions. Ask me anything!",
    "Hey there! Welcome to the Tailored Offers demo. I can explain how our AI agent works. What would you like to know?",
    "Hi! I'm excited to show you how AI agents can transform customer experiences. Where should we start?",
  ],

  whatIsThis: `This is an AI-powered Offer Agent demo for American Airlines.
    The agent analyzes customer data, flight information, and ML predictions to decide
    which upgrade offer to give each customer. It uses a pattern called ReWOO -
    that stands for Reasoning Without Observation - which makes it super efficient!`,

  whyAgents: `Great question! AI Agents are important because they can make complex decisions
    that would take humans much longer. Instead of writing thousands of rules, we give the agent
    goals and let it figure out the best approach. It's like having a super-smart colleague
    who never gets tired and can process millions of customers!`,

  rewooPattern: `ReWOO stands for Reasoning Without Observation. It has three phases:
    First, the PLANNER looks at the customer and decides what to evaluate.
    Then, the WORKER executes all those evaluations in parallel - super fast!
    Finally, the SOLVER synthesizes everything and makes the final decision.
    This is much more efficient than older patterns that go back and forth!`,

  planner: `The Planner is like the brain's planning center. It looks at the customer data
    and asks: What do I need to check before making a decision? Should I check their
    loyalty status? Their price sensitivity? Recent complaints? It creates a smart
    evaluation plan customized for each customer.`,

  worker: `The Worker is the execution engine. Once the Planner creates a plan,
    the Worker runs all the evaluations. It checks ML confidence scores, looks for
    service issues, evaluates price sensitivity, and checks inventory.
    It's like having multiple analysts working in parallel!`,

  solver: `The Solver is the decision maker. It takes all the evidence from the Worker
    and synthesizes it into a final decision. Should we offer Business Class?
    Premium Economy? Should we apply a discount? The Solver weighs all factors
    and picks the optimal offer.`,

  promptEditing: `The prompt editing feature is really powerful! Business users can
    control agent behavior without writing code. Just edit the instructions in plain English.
    Want the agent to be more generous with discounts? Just tell it!
    Want it to prioritize customer satisfaction? Update the prompt!
    Changes take effect immediately.`,

  hitl: `HITL stands for Human In The Loop. When enabled, high-value or risky offers
    get sent to a human reviewer before being sent to the customer.
    This is great for compliance and building trust. The AI makes a recommendation,
    but a human has the final say on important decisions.`,

  mlScores: `The ML scores come from machine learning models that predict how likely
    a customer is to accept each offer. Higher confidence means the model is more sure.
    The agent uses these predictions to choose offers that customers are likely to love!`,

  howToDemo: `Here's how to run the demo:
    First, select a customer from the dropdown - each has a different scenario.
    Then click Run Agent to watch the magic happen!
    You'll see the Planner think, the Worker evaluate, and the Solver decide.
    Try editing prompts to see how behavior changes!`,

  tutorial: `Let me give you a quick tour!
    At the top, you can control agent behavior by editing prompts.
    The pipeline shows data flowing from flights to the final decision.
    On the left, you see input data like customer info and ML scores.
    In the middle, watch the agent's real-time reasoning.
    On the right, see the final offer decision.
    Ready to try it? Select a customer and click Run Agent!`,

  dontKnow: [
    "Hmm, I'm not sure about that one. I'm trained specifically on this demo. Try asking about agents, ReWOO, prompts, or how to run the demo!",
    "That's outside my knowledge area. I know a lot about AI agents and this demo though! What would you like to know about those?",
    "I don't have information about that, but I'd love to tell you about how our intelligent agent works!",
  ],
};

// Pattern matching for questions
function getResponse(input: string): string {
  const lower = input.toLowerCase();

  // Greetings
  if (lower.match(/^(hi|hello|hey|howdy|greetings)/)) {
    return KNOWLEDGE_BASE.greeting[Math.floor(Math.random() * KNOWLEDGE_BASE.greeting.length)];
  }

  // What is this / what does this do
  if (lower.match(/what.*(is this|does this|demo|show|about)/)) {
    return KNOWLEDGE_BASE.whatIsThis;
  }

  // Why agents / importance of agents
  if (lower.match(/(why|importance|important|benefit).*(agent|ai)/)) {
    return KNOWLEDGE_BASE.whyAgents;
  }

  // ReWOO pattern
  if (lower.match(/rewoo|re-woo|pattern|how.*(work|agent work)/)) {
    return KNOWLEDGE_BASE.rewooPattern;
  }

  // Planner
  if (lower.match(/planner|planning|plan phase/)) {
    return KNOWLEDGE_BASE.planner;
  }

  // Worker
  if (lower.match(/worker|execution|evaluat/)) {
    return KNOWLEDGE_BASE.worker;
  }

  // Solver
  if (lower.match(/solver|decision|synthesiz|final/)) {
    return KNOWLEDGE_BASE.solver;
  }

  // Prompt editing
  if (lower.match(/prompt|edit|control|customize|change.*(behavior|agent)/)) {
    return KNOWLEDGE_BASE.promptEditing;
  }

  // HITL
  if (lower.match(/hitl|human.*(loop|review)|approval/)) {
    return KNOWLEDGE_BASE.hitl;
  }

  // ML scores
  if (lower.match(/ml|machine learning|score|predict|confidence/)) {
    return KNOWLEDGE_BASE.mlScores;
  }

  // How to use / demo
  if (lower.match(/how.*(use|run|demo|start|try)/)) {
    return KNOWLEDGE_BASE.howToDemo;
  }

  // Tutorial
  if (lower.match(/tutorial|tour|guide|explain|walk.*through|show me/)) {
    return KNOWLEDGE_BASE.tutorial;
  }

  // Don't know
  return KNOWLEDGE_BASE.dontKnow[Math.floor(Math.random() * KNOWLEDGE_BASE.dontKnow.length)];
}

// Check if speech recognition is available
const isSpeechRecognitionAvailable = () => {
  return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
};

// Check if speech synthesis is available
const isSpeechSynthesisAvailable = () => {
  return 'speechSynthesis' in window;
};

interface FloatingRobotProps {
  onSpeaking?: (isSpeaking: boolean) => void;
}

export function FloatingRobot({ onSpeaking }: FloatingRobotProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'robot'; text: string }>>([]);
  const [inputText, setInputText] = useState('');
  const [showWelcome, setShowWelcome] = useState(true);

  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize speech recognition
  useEffect(() => {
    if (isSpeechRecognitionAvailable()) {
      const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;

      recognitionRef.current.onresult = (event: any) => {
        const current = event.resultIndex;
        const transcriptText = event.results[current][0].transcript;
        setTranscript(transcriptText);

        if (event.results[current].isFinal) {
          handleUserInput(transcriptText);
          setTranscript('');
        }
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };
    }
  }, []);

  // Speak text
  const speak = useCallback((text: string) => {
    if (!isSpeechSynthesisAvailable()) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    utterance.volume = 1.0;

    // Try to get a nice voice
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(v =>
      v.name.includes('Samantha') ||
      v.name.includes('Google') ||
      v.name.includes('Microsoft') ||
      v.lang.startsWith('en')
    );
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      onSpeaking?.(true);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      onSpeaking?.(false);
    };

    window.speechSynthesis.speak(utterance);
  }, [onSpeaking]);

  // Handle user input
  const handleUserInput = useCallback((text: string) => {
    if (!text.trim()) return;

    // Add user message
    setMessages(prev => [...prev, { role: 'user', text }]);

    // Get response
    const response = getResponse(text);

    // Add robot response after a small delay
    setTimeout(() => {
      setMessages(prev => [...prev, { role: 'robot', text: response }]);
      speak(response);
    }, 500);
  }, [speak]);

  // Start listening
  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      setIsListening(true);
      recognitionRef.current.start();
    }
  };

  // Stop listening
  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  };

  // Handle text input
  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputText.trim()) {
      handleUserInput(inputText);
      setInputText('');
    }
  };

  // Welcome message
  const showWelcomeMessage = () => {
    setShowWelcome(false);
    const welcome = KNOWLEDGE_BASE.greeting[0];
    setMessages([{ role: 'robot', text: welcome }]);
    speak(welcome);
  };

  // Stop speaking
  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    onSpeaking?.(false);
  };

  return (
    <>
      {/* Floating Robot Button */}
      <div className="fixed bottom-6 right-6 z-50">
        {/* Speech bubble hint */}
        {!isOpen && showWelcome && (
          <div className="absolute bottom-full right-0 mb-2 animate-bounce">
            <div className="bg-white text-slate-800 rounded-2xl px-4 py-2 shadow-lg text-sm max-w-[200px]">
              <span>Hi! Click me for a tour! 🎯</span>
              <div className="absolute bottom-0 right-8 transform translate-y-1/2 rotate-45 w-3 h-3 bg-white"></div>
            </div>
          </div>
        )}

        {/* Robot button */}
        <button
          onClick={() => {
            setIsOpen(!isOpen);
            if (!isOpen && showWelcome) {
              showWelcomeMessage();
            }
          }}
          className={`w-16 h-16 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 ${
            isOpen
              ? 'bg-gradient-to-br from-cyan-500 to-blue-600 scale-90'
              : 'bg-gradient-to-br from-cyan-400 to-blue-500 hover:scale-110'
          } ${isSpeaking ? 'animate-pulse' : ''}`}
        >
          {/* Robot face */}
          <div className="relative">
            <span className="text-3xl">{isListening ? '👂' : isSpeaking ? '🗣️' : '🤖'}</span>
            {isListening && (
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
            )}
          </div>
        </button>
      </div>

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 max-h-[500px] bg-slate-900 rounded-2xl shadow-2xl border border-cyan-500/30 z-50 flex flex-col overflow-hidden animate-slideUp">
          {/* Header */}
          <div className="bg-gradient-to-r from-cyan-600 to-blue-600 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{isSpeaking ? '🗣️' : '🤖'}</span>
              <div>
                <div className="font-bold text-white">Demo Assistant</div>
                <div className="text-xs text-cyan-100">
                  {isSpeaking ? 'Speaking...' : isListening ? 'Listening...' : 'Ask me anything!'}
                </div>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/80 hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[300px]">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                    msg.role === 'user'
                      ? 'bg-cyan-600 text-white rounded-br-sm'
                      : 'bg-slate-700 text-slate-100 rounded-bl-sm'
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}

            {/* Listening indicator */}
            {isListening && transcript && (
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-cyan-600/50 text-white/70 rounded-br-sm italic">
                  {transcript}...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Actions */}
          <div className="px-4 py-2 border-t border-slate-700 flex gap-2 flex-wrap">
            <button
              onClick={() => handleUserInput("Give me a tutorial")}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded-full transition-colors"
            >
              📚 Tutorial
            </button>
            <button
              onClick={() => handleUserInput("Why are agents important?")}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded-full transition-colors"
            >
              🤔 Why Agents?
            </button>
            <button
              onClick={() => handleUserInput("Explain ReWOO pattern")}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded-full transition-colors"
            >
              🔄 ReWOO
            </button>
            <button
              onClick={() => handleUserInput("How do I edit prompts?")}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded-full transition-colors"
            >
              ✏️ Prompts
            </button>
          </div>

          {/* Input Area */}
          <div className="p-3 border-t border-slate-700">
            <form onSubmit={handleTextSubmit} className="flex gap-2">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type or use voice..."
                className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-4 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              />

              {/* Voice button */}
              {isSpeechRecognitionAvailable() && (
                <button
                  type="button"
                  onClick={isListening ? stopListening : startListening}
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                    isListening
                      ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                      : 'bg-slate-700 hover:bg-slate-600'
                  }`}
                >
                  <span className="text-lg">{isListening ? '⏹️' : '🎤'}</span>
                </button>
              )}

              {/* Stop speaking button */}
              {isSpeaking && (
                <button
                  type="button"
                  onClick={stopSpeaking}
                  className="w-10 h-10 rounded-xl bg-amber-500 hover:bg-amber-600 flex items-center justify-center transition-all"
                >
                  <span className="text-lg">🔇</span>
                </button>
              )}

              {/* Send button */}
              <button
                type="submit"
                className="w-10 h-10 rounded-xl bg-cyan-600 hover:bg-cyan-500 flex items-center justify-center transition-all"
              >
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </form>

            {/* Voice hint */}
            {isSpeechRecognitionAvailable() && !isListening && (
              <div className="text-center text-xs text-slate-500 mt-2">
                🎤 Click the mic to speak, or type your question
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
