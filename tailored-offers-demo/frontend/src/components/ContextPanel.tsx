import type { EnrichedPNR } from '../types';

interface Props {
  data: EnrichedPNR | null;
}

const tierColors: Record<string, string> = {
  'Gold': 'bg-yellow-100 text-yellow-800',
  'Platinum': 'bg-gray-200 text-gray-800',
  'Platinum Pro': 'bg-gray-300 text-gray-900',
  'Executive Platinum': 'bg-purple-100 text-purple-800',
  'General': 'bg-slate-100 text-slate-600',
};

export function ContextPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <p className="text-gray-500 text-center">Select a PNR to view details</p>
      </div>
    );
  }

  const { customer, flight, reservation, ml_scores } = data;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="grid md:grid-cols-2 gap-6">
        {/* Customer Card */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Customer Profile
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-lg font-semibold text-gray-800">{customer.name}</span>
              <span className={`px-2 py-1 rounded text-sm font-medium ${tierColors[customer.loyalty_tier] || tierColors['General']}`}>
                {customer.loyalty_tier}
              </span>
            </div>
            <div className="text-sm text-gray-600">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Tenure</span>
                <span className="font-medium">{Math.floor(customer.tenure_days / 365)} years</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Travel Pattern</span>
                <span className="font-medium capitalize">{customer.travel_pattern}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Annual Revenue</span>
                <span className="font-medium">${customer.annual_revenue.toLocaleString()}</span>
              </div>
              {customer.historical_upgrades && (
                <div className="flex justify-between py-1">
                  <span>Upgrade Accept Rate</span>
                  <span className="font-medium">
                    {(customer.historical_upgrades.acceptance_rate * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>
            {customer.is_suppressed && (
              <div className="mt-2 bg-red-50 text-red-700 px-3 py-2 rounded-lg text-sm">
                ⚠️ Suppressed: {customer.complaint_reason || 'Recent complaint'}
              </div>
            )}
          </div>
        </div>

        {/* Flight Card */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Flight Details
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-lg font-semibold text-gray-800">{flight.flight_id}</span>
              <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-medium">
                T-{reservation.hours_to_departure}hrs
              </span>
            </div>
            <div className="text-sm text-gray-600 mb-3">
              {flight.route}
            </div>
            <div className="text-sm text-gray-600">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Departure</span>
                <span className="font-medium">{flight.departure_date} {flight.departure_time}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Current Cabin</span>
                <span className="font-medium capitalize">{reservation.current_cabin.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Fare Class</span>
                <span className="font-medium">{reservation.fare_class}</span>
              </div>
            </div>

            {/* Cabin inventory */}
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Cabin Inventory</div>
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(flight.cabins).map(([cabin, data]) => (
                  <div
                    key={cabin}
                    className={`text-center p-2 rounded ${
                      data.needs_treatment ? 'bg-amber-50 border border-amber-200' : 'bg-gray-50'
                    }`}
                  >
                    <div className="text-xs text-gray-500 capitalize">{cabin.replace('_', ' ')}</div>
                    <div className="font-semibold text-gray-800">{(data.load_factor * 100).toFixed(0)}%</div>
                    <div className="text-xs text-gray-400">{data.available_seats} seats</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ML Scores */}
      {ml_scores && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            ML Propensity Scores
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {ml_scores.propensity_scores && Object.entries(ml_scores.propensity_scores).map(([offer, scores]: [string, any]) => (
              <div key={offer} className="bg-gray-50 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 uppercase">{offer.replace('_', ' ')}</div>
                <div className="text-2xl font-bold text-blue-600">{(scores.p_buy * 100).toFixed(0)}%</div>
                <div className="text-xs text-gray-400">P(buy)</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
