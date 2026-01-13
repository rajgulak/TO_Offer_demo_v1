import type { AgentStatus } from '../types';

interface Props {
  id: string;
  name: string;
  shortName: string;
  icon: string;
  status: AgentStatus;
  summary?: string;
  isSelected: boolean;
  onClick: () => void;
  step: number;
}

const icons: Record<string, string> = {
  brain: '🧠',
  chart: '📊',
  scale: '⚖️',
  sparkles: '✨',
  phone: '📱',
  trending: '📈',
};

const statusStyles: Record<AgentStatus, string> = {
  pending: 'bg-gray-100 border-gray-300 text-gray-400',
  processing: 'bg-blue-50 border-blue-400 text-blue-600 processing',
  complete: 'bg-emerald-50 border-emerald-400 text-emerald-600',
  skipped: 'bg-amber-50 border-amber-400 text-amber-600',
  error: 'bg-red-50 border-red-400 text-red-600',
};

const statusIcons: Record<AgentStatus, string> = {
  pending: '○',
  processing: '◐',
  complete: '✓',
  skipped: '—',
  error: '✗',
};

export function AgentNode({ id: _id, name: _name, shortName, icon, status, summary, isSelected, onClick, step }: Props) {
  // _id and _name are available for future use (e.g., accessibility, data attributes)
  void _id; void _name;
  return (
    <div
      onClick={onClick}
      className={`
        agent-node relative flex flex-col items-center cursor-pointer
        ${status === 'processing' ? 'processing' : ''}
      `}
    >
      {/* Step number */}
      <div className="absolute -top-2 -left-2 w-6 h-6 rounded-full bg-gray-700 text-white text-xs flex items-center justify-center font-bold">
        {step}
      </div>

      {/* Main node */}
      <div
        className={`
          w-24 h-24 rounded-2xl border-2 flex flex-col items-center justify-center
          transition-all duration-300 ${statusStyles[status]}
          ${isSelected ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
          ${status === 'processing' ? 'shadow-lg shadow-blue-200' : ''}
        `}
      >
        {/* Icon */}
        <span className="text-3xl mb-1">{icons[icon] || '🔧'}</span>

        {/* Status indicator */}
        <span className={`text-lg font-bold ${status === 'complete' ? 'text-emerald-500' : ''}`}>
          {statusIcons[status]}
        </span>
      </div>

      {/* Label */}
      <div className="mt-2 text-center">
        <div className="text-sm font-semibold text-gray-700">{shortName}</div>
        {summary && status !== 'pending' && (
          <div className="text-xs text-gray-500 max-w-[120px] truncate mt-0.5">
            {summary}
          </div>
        )}
      </div>
    </div>
  );
}
