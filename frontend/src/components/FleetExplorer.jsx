import React, { useState, useEffect } from 'react';
import { Truck, Search, ShieldAlert, Wrench, AlertTriangle, Flame, Navigation, MapPin } from 'lucide-react';

export default function FleetExplorer({ apiBase = 'http://127.0.0.1:8000' }) {
  const [fleet, setFleet] = useState([]);
  const [topology, setTopology] = useState({ coordinates: {}, distances: [] });
  const [search, setSearch] = useState('');
  const [filterHub, setFilterHub] = useState('ALL');
  const [filterJugaadOnly, setFilterJugaadOnly] = useState(false);
  const [filterOverdueOnly, setFilterOverdueOnly] = useState(false);

  // Distance calculator
  const [originHub, setOriginHub] = useState('Delhi');
  const [destHub, setDestHub] = useState('Gurgaon');

  useEffect(() => {
    fetch(`${apiBase}/api/fleet`)
      .then(res => res.json())
      .then(data => setFleet(data))
      .catch(err => console.error('Failed to load fleet:', err));

    fetch(`${apiBase}/api/topology`)
      .then(res => res.json())
      .then(data => setTopology(data))
      .catch(err => console.error('Failed to load topology:', err));
  }, []);

  const hubs = ['ALL', ...Array.from(new Set(fleet.map(f => f.home_hub).filter(Boolean)))];

  const filteredFleet = fleet.filter(v => {
    const matchesSearch = v.reg.toLowerCase().includes(search.toLowerCase()) || 
                          (v.model && v.model.toLowerCase().includes(search.toLowerCase()));
    const matchesHub = filterHub === 'ALL' || v.home_hub === filterHub;
    const matchesJugaad = !filterJugaadOnly || v.has_jugaad;
    const matchesOverdue = !filterOverdueOnly || v.is_overdue;

    return matchesSearch && matchesHub && matchesJugaad && matchesOverdue;
  });

  const getDistance = (h1, h2) => {
    if (h1 === h2) return 0;
    const match = topology.distances.find(
      d => (d.origin === h1 && d.destination === h2) || (d.origin === h2 && d.destination === h1)
    );
    return match ? match.distance_km : 500;
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-2">
      {/* Header & Distance Quick Tool */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e8e8e6]">
        <div>
          <span className="notion-tag font-mono text-[10px] uppercase tracking-wider">
            FLEET INVENTORY & TOPOLOGY
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#191919] serif-heading mt-1">
            North India Fleet Database ({fleet.length} Units)
          </h1>
          <p className="text-xs text-[#787774] mt-1">
            Fleet health indicators, Guddu jugaad 7-day timers, engine heaters, and BS4/BS6 winter GRAP compliance.
          </p>
        </div>

        {/* Distance Tool */}
        <div className="bg-[#fbfbfa] p-2.5 rounded-lg border border-[#e8e8e6] flex items-center gap-2 text-xs">
          <Navigation className="w-3.5 h-3.5 text-[#787774]" />
          <select
            value={originHub}
            onChange={e => setOriginHub(e.target.value)}
            className="bg-[#ffffff] border border-[#d3d3d0] rounded px-2 py-0.5 text-xs text-[#191919]"
          >
            {Object.keys(topology.coordinates).map(h => <option key={h} value={h}>{h}</option>)}
          </select>
          <span className="text-[#9b9a97]">to</span>
          <select
            value={destHub}
            onChange={e => setDestHub(e.target.value)}
            className="bg-[#ffffff] border border-[#d3d3d0] rounded px-2 py-0.5 text-xs text-[#191919]"
          >
            {Object.keys(topology.coordinates).map(h => <option key={h} value={h}>{h}</option>)}
          </select>
          <span className="font-mono font-bold text-[#191919] ml-1">
            = {getDistance(originHub, destHub)} km
          </span>
        </div>
      </div>

      {/* Filter Controls (Notion style) */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-3.5 h-3.5 text-[#9b9a97] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search vehicle plate (e.g. UP40IM3144) or model..."
            className="w-full bg-[#fbfbfa] border border-[#d3d3d0] rounded-md pl-8 pr-3 py-1.5 text-xs text-[#191919] placeholder-[#9b9a97] focus:outline-none focus:border-[#242424]"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {hubs.map(h => (
            <button
              key={h}
              onClick={() => setFilterHub(h)}
              className={`px-2.5 py-1 rounded text-xs font-medium shrink-0 transition-all ${
                filterHub === h
                  ? 'bg-[#242424] text-white'
                  : 'bg-[#f1f1ef] text-[#787774] hover:text-[#191919]'
              }`}
            >
              {h}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setFilterJugaadOnly(!filterJugaadOnly)}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 transition-all ${
              filterJugaadOnly
                ? 'bg-[#fef3c7] text-[#92400e] border border-[#fde68a]'
                : 'bg-[#f1f1ef] text-[#787774]'
            }`}
          >
            <Wrench className="w-3 h-3" /> Guddu Jugaad Active
          </button>
          <button
            onClick={() => setFilterOverdueOnly(!filterOverdueOnly)}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 transition-all ${
              filterOverdueOnly
                ? 'bg-[#fee2e2] text-[#991b1b] border border-[#fecaca]'
                : 'bg-[#f1f1ef] text-[#787774]'
            }`}
          >
            <AlertTriangle className="w-3 h-3" /> Overdue (&gt;30d)
          </button>
        </div>
      </div>

      {/* Database Table (Notion clean aesthetic) */}
      <div className="notion-card overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#fbfbfa] text-[#787774] font-mono text-[10px] uppercase border-b border-[#e8e8e6]">
            <tr>
              <th className="p-3">Registration Plate</th>
              <th className="p-3">Model & Year</th>
              <th className="p-3">Home Hub</th>
              <th className="p-3">Emission</th>
              <th className="p-3">Engine Heater</th>
              <th className="p-3">Service Health</th>
              <th className="p-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ededeb]">
            {filteredFleet.map((v, idx) => (
              <tr key={idx} className="hover:bg-[#fbfbfa] transition-colors">
                <td className="p-3 font-mono font-bold text-[#191919]">{v.reg}</td>
                <td className="p-3 text-[#2f2f2f]">{v.model} ({v.year})</td>
                <td className="p-3">
                  <span className="notion-tag font-mono text-[10px]">{v.home_hub}</span>
                </td>
                <td className="p-3 font-mono font-medium text-[#2f2f2f]">{v.bs_stage}</td>
                <td className="p-3 text-[#787774]">
                  {v.engine_heater === 'Yes' ? (
                    <span className="text-[#15803d] font-medium flex items-center gap-1"><Flame className="w-3 h-3 text-amber-500" /> Yes</span>
                  ) : 'No'}
                </td>
                <td className="p-3">
                  {v.is_overdue ? (
                    <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#fee2e2] text-[#991b1b] border border-[#fecaca]">
                      Overdue (&gt;30d)
                    </span>
                  ) : v.has_jugaad ? (
                    <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                      Guddu Jugaad (7d Lock)
                    </span>
                  ) : (
                    <span className="text-[#15803d]">Healthy</span>
                  )}
                </td>
                <td className="p-3">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                    v.status === 'Active' ? 'bg-[#dcfce7] text-[#166534]' : 'bg-[#f1f1ef] text-[#787774]'
                  }`}>
                    {v.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
