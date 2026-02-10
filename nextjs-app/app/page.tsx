'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { RefreshCw, Search, MapPin, Star, ExternalLink, Clock } from 'lucide-react';

// Initialize Supabase Client
const supabaseUrl = 'https://lvevatkufgiwzmcyyuon.supabase.co';
// Using the key you provided. If this fails, we need the "anon public" key (starts with ey...)
const supabaseKey = 'sb_publishable__wrYX8B_kRbXoERoGGuJEg_ubVrT4rh';
const supabase = createClient(supabaseUrl, supabaseKey);

interface Lead {
  id: string;
  title: string;
  link: string;
  region: string;
  score: number;
  keyword: string;
  classification: string;
  timestamp: string;
  is_new: boolean;
}

export default function Dashboard() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  async function fetchLeads() {
    setLoading(true);
    // Fetch from Supabase
    const { data, error } = await supabase
      .from('leads')
      .select('*')
      .order('score', { ascending: false })
      .limit(100);

    if (error) {
      console.error('Error fetching leads:', error);
      // Fallback to static data if DB is empty or connection fails
      setLeads([]);
    } else {
      setLeads(data || []);
      if (data && data.length > 0) {
        setLastUpdated(new Date().toLocaleTimeString());
      }
    }
    setLoading(false);
  }

  useEffect(() => {
    fetchLeads();
  }, []);

  return (
    <div className="min-h-screen bg-[#0f0d0b] text-[#f5f0e8] font-sans selection:bg-[#cd7f32] selection:text-white">

      {/* Header */}
      <header className="border-b border-[#352a22] bg-[#1e1914]/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#cd7f32] rounded-lg flex items-center justify-center shadow-lg shadow-orange-900/20">
              <span className="text-2xl">⚙️</span>
            </div>
            <div>
              <h1 className="font-bold text-xl tracking-wide uppercase text-white">OldTimeCrank</h1>
              <p className="text-xs text-[#9a8a78] tracking-widest hidden sm:block">Antique Phonograph Intelligence</p>
            </div>
          </div>

          <button
            onClick={fetchLeads}
            disabled={loading}
            className="flex items-center gap-2 bg-[#5c4033] hover:bg-[#cd7f32] text-white px-4 py-2 rounded-full text-sm font-semibold transition-all border border-[#352a22] hover:border-[#cd7f32] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Scanning...' : 'Refresh Data'}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-[#1e1914] p-4 rounded-xl border border-[#352a22]">
            <p className="text-[#9a8a78] text-xs uppercase tracking-wider mb-1">Total Finds</p>
            <p className="text-3xl font-bold text-white">{leads.length}</p>
          </div>
          <div className="bg-[#1e1914] p-4 rounded-xl border border-[#352a22]">
            <p className="text-[#9a8a78] text-xs uppercase tracking-wider mb-1">Gold Tier</p>
            <p className="text-3xl font-bold text-[#ffd700]">{leads.filter(l => l.score >= 4).length}</p>
          </div>
          <div className="bg-[#1e1914] p-4 rounded-xl border border-[#352a22]">
            <p className="text-[#9a8a78] text-xs uppercase tracking-wider mb-1">Regions</p>
            <p className="text-3xl font-bold text-[#cd7f32]">{new Set(leads.map(l => l.region)).size}</p>
          </div>
          <div className="bg-[#1e1914] p-4 rounded-xl border border-[#352a22]">
            <p className="text-[#9a8a78] text-xs uppercase tracking-wider mb-1">Last Update</p>
            <p className="text-lg font-medium text-white flex items-center gap-2 h-full">
              <Clock className="w-4 h-4 text-[#4caf50]" />
              {lastUpdated || 'Pending'}
            </p>
          </div>
        </div>

        {/* Listings */}
        {loading && leads.length === 0 ? (
          <div className="text-center py-20 text-[#9a8a78]">
            <div className="animate-spin w-8 h-8 border-2 border-[#cd7f32] border-t-transparent rounded-full mx-auto mb-4"></div>
            <p>Connecting to satellite feeds...</p>
          </div>
        ) : leads.length === 0 ? (
          <div className="text-center py-20 bg-[#1e1914] rounded-2xl border border-[#352a22]">
            <p className="text-xl text-[#9a8a78]">Database initialized. Waiting for first ingestion event.</p>
            <p className="text-sm text-[#5c4033] mt-2">Trigger the scraper to populate data.</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {leads.map((lead) => (
              <div
                key={lead.id}
                className={`group relative bg-[#1e1914] rounded-xl p-5 border transition-all hover:-translate-y-1 hover:shadow-2xl ${lead.score >= 4
                    ? 'border-[#ffd700]/30 shadow-[0_0_15px_-3px_rgba(255,215,0,0.1)]'
                    : 'border-[#352a22] hover:border-[#cd7f32]/50'
                  }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <span className="bg-[#0f0d0b] text-[#9a8a78] text-[10px] uppercase font-bold px-2 py-1 rounded flex items-center gap-1">
                    <MapPin className="w-3 h-3" /> {lead.region || 'FL'}
                  </span>
                  {lead.score >= 4 && (
                    <span className="bg-[#ffd700] text-black text-[10px] uppercase font-bold px-2 py-1 rounded flex items-center gap-1">
                      <Star className="w-3 h-3 fill-black" /> Gold Find
                    </span>
                  )}
                </div>

                <h3 className="font-semibold text-lg leading-tight mb-2 text-white group-hover:text-[#cd7f32] transition-colors line-clamp-2">
                  {lead.title}
                </h3>

                <div className="flex items-center gap-2 mb-4">
                  <div className="flex-1 h-1.5 bg-[#352a22] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${lead.score >= 4 ? 'bg-[#ffd700]' : 'bg-[#cd7f32]'}`}
                      style={{ width: `${(lead.score / 5) * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-xs font-mono text-[#9a8a78]">{lead.score}/5.0</span>
                </div>

                <div className="flex items-center justify-between text-xs text-[#9a8a78] mt-4 pt-4 border-t border-[#352a22]">
                  <span className="capitalize">{lead.classification.replace(/_/g, ' ')}</span>
                  <a
                    href={lead.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[#cd7f32] hover:text-[#ffd700] font-medium transition-colors"
                  >
                    View Listing <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
