export function Header() {
  return (
    <header className="bg-gradient-to-r from-red-700 to-red-600 text-white py-4 px-6 shadow-lg">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="text-3xl font-bold tracking-tight">AA</div>
          <div className="border-l border-white/30 pl-4">
            <h1 className="text-xl font-semibold">Tailored Offers</h1>
            <p className="text-sm text-white/80">Agentic AI Demo - MVP1</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-sm">
          <span className="bg-slate-500/80 px-3 py-1 rounded-full">4 Workflows</span>
          <span className="bg-blue-500/80 px-3 py-1 rounded-full">1 Agent</span>
          <span className="bg-purple-500/80 px-3 py-1 rounded-full">1 LLM Call</span>
        </div>
      </div>
    </header>
  );
}
