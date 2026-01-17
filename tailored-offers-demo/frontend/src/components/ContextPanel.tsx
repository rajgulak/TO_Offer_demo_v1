import type { EnrichedPNR } from '../types';

interface Props {
  data: EnrichedPNR | null;
}

// Loyalty tier display names and colors
const tierInfo: Record<string, { name: string; color: string }> = {
  'E': { name: 'Executive Platinum', color: 'bg-purple-100 text-purple-800' },
  'C': { name: 'Concierge Key', color: 'bg-indigo-100 text-indigo-800' },
  'T': { name: 'Platinum Pro', color: 'bg-gray-300 text-gray-900' },
  'P': { name: 'Platinum', color: 'bg-gray-200 text-gray-800' },
  'G': { name: 'Gold', color: 'bg-yellow-100 text-yellow-800' },
  'R': { name: 'AAdvantage', color: 'bg-slate-100 text-slate-600' },
  'N': { name: 'Non-member', color: 'bg-slate-50 text-slate-500' },
};

// Cabin code display names
const cabinNames: Record<string, string> = {
  'F': 'Business/First',
  'W': 'Premium Economy',
  'MCE': 'Main Cabin Extra',
  'Y': 'Main Cabin',
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
  const tier = tierInfo[customer.loyalty_tier] || { name: customer.loyalty_tier, color: 'bg-slate-100 text-slate-600' };

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
              <span className={`px-2 py-1 rounded text-sm font-medium ${tier.color}`}>
                {tier.name}
              </span>
            </div>
            <div className="text-sm text-gray-600">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Tenure</span>
                <span className="font-medium">{Math.floor((customer.aadv_tenure_days || 0) / 365)} years</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Travel Pattern</span>
                <span className="font-medium capitalize">
                  {(customer.business_trip_likelihood || 0) > 0.5 ? 'Business' : 'Leisure'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>TTM Revenue</span>
                <span className="font-medium">${(customer.flight_revenue_amt_history || 0).toLocaleString()}</span>
              </div>
              {customer.historical_upgrades && (
                <div className="flex justify-between py-1">
                  <span>Upgrade Accept Rate</span>
                  <span className="font-medium">
                    {((customer.historical_upgrades.acceptance_rate || 0) * 100).toFixed(0)}%
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
              <span className="text-lg font-semibold text-gray-800">AA{flight.operat_flight_nbr}</span>
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
                <span className="font-medium">{flight.leg_dep_dt} {flight.schd_leg_dep_lcl_tms?.slice(11, 16) || ''}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Current Cabin</span>
                <span className="font-medium">{cabinNames[reservation.max_bkd_cabin_cd] || reservation.max_bkd_cabin_cd}</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Fare Class</span>
                <span className="font-medium">{reservation.fare_class}</span>
              </div>
            </div>

            {/* Cabin inventory */}
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Cabin Inventory</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(flight.cabins || {}).map(([cabinCode, cabinData]: [string, any]) => {
                  const lf = cabinData.expected_load_factor || 0;
                  const available = cabinData.cabin_available || 0;
                  const needsTreatment = lf < 0.85 && available >= 2;
                  return (
                    <div
                      key={cabinCode}
                      className={`text-center p-2 rounded ${
                        needsTreatment ? 'bg-amber-50 border border-amber-200' : 'bg-gray-50'
                      }`}
                    >
                      <div className="text-xs text-gray-500">{cabinNames[cabinCode] || cabinCode}</div>
                      <div className="font-semibold text-gray-800">{(lf * 100).toFixed(0)}%</div>
                      <div className="text-xs text-gray-400">{available} avail</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ML Scores */}
      {ml_scores && ml_scores.propensity_scores && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            ML Propensity Scores (by product & price)
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(ml_scores.propensity_scores).map(([offer, scores]: [string, any]) => {
              // Get the price points and find the highest P(buy)
              const pricePoints = scores.price_points || {};
              const prices = Object.keys(pricePoints).map(Number).sort((a, b) => a - b);
              const midPrice = prices[Math.floor(prices.length / 2)] || prices[0];
              const pBuy = pricePoints[midPrice]?.p_buy || 0;

              return (
                <div key={offer} className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 uppercase mb-1">{offer.replace(/_/g, ' ')}</div>
                  <div className="text-2xl font-bold text-blue-600">{(pBuy * 100).toFixed(0)}%</div>
                  <div className="text-xs text-gray-400">P(buy) @ ${midPrice}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    Range: ${prices[0]} - ${prices[prices.length - 1]}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
