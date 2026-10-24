import React, { useState, useEffect } from 'react';
import {
  PlusCircle,
  Building2,
  MapPin,
  GitBranch,
  Database,
  CheckCircle2,
  RotateCcw,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { api } from '../api';

interface DataStudioViewProps {
  onDataUpdated: () => void;
  onAskAboutCompany: (question: string) => void;
}

const INDIAN_CITY_PRESETS = [
  'Gwalior',
  'Morena',
  'Jaipur',
  'Ajmer',
  'Bhopal',
  'Katni',
  'Ahmedabad / Gandhinagar',
  'Mumbai',
];

const FACILITY_OPTIONS = [
  { id: 'FAC-GWL', label: 'FAC-GWL — Gwalior Heavy Engineering Hub (Gwalior)' },
  { id: 'FAC-MRN', label: 'FAC-MRN — Morena Solar & Grid Sub-Station (Morena)' },
  { id: 'FAC-JPR', label: 'FAC-JPR — Jaipur PinkCity Semiconductor Fab (Jaipur)' },
  { id: 'FAC-AJM', label: 'FAC-AJM — Ajmer Precision Avionics Plant (Ajmer)' },
  { id: 'FAC-BPL', label: 'FAC-BPL — Bhopal Bio-Pharma & Cleanroom Park (Bhopal)' },
  { id: 'FAC-KTN', label: 'FAC-KTN — Katni Defence Metallurgy Foundry (Katni)' },
  { id: 'FAC-AMD', label: 'FAC-AMD — Ahmedabad-Gandhinagar GIFT Cloud Hub' },
  { id: 'FAC-MUM', label: 'FAC-MUM — Mumbai Nariman Enterprise Data Core (Mumbai)' },
];

export const DataStudioView: React.FC<DataStudioViewProps> = ({
  onDataUpdated,
  onAskAboutCompany,
}) => {
  const [vendorName, setVendorName] = useState<string>('');
  const [city, setCity] = useState<string>('Gwalior');
  const [primaryProduct, setPrimaryProduct] = useState<string>('');
  const [facilityId, setFacilityId] = useState<string>('FAC-GWL');
  const [tierLevel, setTierLevel] = useState<number>(1);
  const [complianceScore, setComplianceScore] = useState<number>(96.0);
  const [contractValueUsd, setContractValueUsd] = useState<number>(4200000);
  const [contractStatus, setContractStatus] = useState<string>('ACTIVE');

  const [submittingCompany, setSubmittingCompany] = useState<boolean>(false);
  const [companyResult, setCompanyResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Graph relationship form state
  const [nodes, setNodes] = useState<any[]>([]);
  const [vendorsList, setVendorsList] = useState<any[]>([]);
  const [sourceEntityId, setSourceEntityId] = useState<string>('');
  const [targetEntityId, setTargetEntityId] = useState<string>('');
  const [relType, setRelType] = useState<string>('SUPPLIES_TO');
  const [relExcerpt, setRelExcerpt] = useState<string>('');
  const [relResult, setRelResult] = useState<any>(null);

  const loadCurrentData = async () => {
    try {
      const [g, sqlRes] = await Promise.all([
        api.getGraph({ source_id: 'enterprise_supply_ops', include_inferred: true }),
        api.executeSql(
          'enterprise_supply_ops',
          'SELECT v.vendor_id, v.vendor_name, v.country, v.tier_level, v.compliance_score, v.primary_product, COALESCE(SUM(c.contract_value_usd), 0) AS contract_usd FROM vendors v LEFT JOIN procurement_contracts c ON v.vendor_id = c.vendor_id GROUP BY v.vendor_id ORDER BY v.vendor_id',
          'List current Indian companies',
          false
        ),
      ]);
      const nodeList = g.nodes || [];
      setNodes(nodeList);
      if (nodeList.length >= 2 && !sourceEntityId) {
        setSourceEntityId(nodeList[0].id);
        setTargetEntityId(nodeList[1].id);
      }
      setVendorsList(sqlRes.rows || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadCurrentData();
  }, []);

  const handleAddCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vendorName.trim()) return;
    setSubmittingCompany(true);
    setErrorMsg(null);
    setCompanyResult(null);
    try {
      const res = await api.addCompany({
        vendor_name: vendorName.trim(),
        city: city.trim() || 'Gwalior',
        tier_level: Number(tierLevel),
        compliance_score: Number(complianceScore),
        primary_product: primaryProduct.trim() || 'Industrial & Enterprise Systems',
        contract_value_usd: Number(contractValueUsd),
        facility_id: facilityId,
        contract_status: contractStatus,
      });
      setCompanyResult(res);
      setVendorName('');
      setPrimaryProduct('');
      await loadCurrentData();
      onDataUpdated();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add company record.');
    } finally {
      setSubmittingCompany(false);
    }
  };

  const handleAddRelationship = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceEntityId || !targetEntityId) return;
    setErrorMsg(null);
    try {
      const res = await api.addRelationship({
        source_entity_id: sourceEntityId,
        target_entity_id: targetEntityId,
        rel_type: relType,
        excerpt:
          relExcerpt.trim() ||
          `Direct relationship (${relType}) added by user in Data Studio.`,
        is_inferred: false,
      });
      setRelResult(res);
      setRelExcerpt('');
      await loadCurrentData();
      onDataUpdated();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add graph relationship.');
    }
  };

  const handleReset = async () => {
    await api.resetData();
    setCompanyResult(null);
    setRelResult(null);
    await loadCurrentData();
    onDataUpdated();
  };

  return (
    <div className="max-w-[1220px] mx-auto space-y-12">
      {/* Top Banner */}
      <div className="rounded-3xl glass-panel-elevated spotlight-card p-8 sm:p-10 flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-2 max-w-3xl">
          <span className="eye-label block">USER-DRIVEN INDIAN ENTERPRISE DATA STUDIO</span>
          <h2 className="text-2xl sm:text-4xl font-display font-bold text-white">
            Add Your Own Companies, Cities & Graph Nodes
          </h2>
          <p className="text-base text-blue-100/80 leading-relaxed font-light">
            Your database and Knowledge Graph are pre-configured with Indian corporate leaders (
            <strong className="text-white">
              Larsen & Toubro, Bharat Forge, Adani Green Energy, Mahindra & Mahindra, Reliance Industries, TCS, Infosys, Biocon
            </strong>
            ) across{' '}
            <strong className="text-[#88ccff]">
              Gwalior, Morena, Jaipur, Ajmer, Bhopal, Katni, Ahmedabad / Gandhinagar, and Mumbai
            </strong>
            . Use the forms below to add any new company, contract, or graph connection anytime.
          </p>
        </div>

        <button
          type="button"
          onClick={handleReset}
          className="px-5 py-3 rounded-xl bg-blue-950/80 hover:bg-blue-900/70 border border-blue-400/35 text-xs font-mono uppercase tracking-wider text-cyan-200 flex items-center gap-2 transition"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset Default Indian Dataset</span>
        </button>
      </div>

      {errorMsg && (
        <div className="p-5 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-sm font-mono text-rose-200">
          {errorMsg}
        </div>
      )}

      {/* Main Two-Column Builder */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left 7 cols: Add Indian Company + Contract + Graph Node */}
        <form
          onSubmit={handleAddCompany}
          className="lg:col-span-7 rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-6"
        >
          <div className="flex items-center gap-3 border-b border-blue-400/20 pb-4">
            <Building2 className="w-6 h-6 text-cyan-300" />
            <div>
              <h3 className="text-xl font-display font-bold text-white">
                1. Add New Indian Company & Procurement Contract
              </h3>
              <p className="text-sm text-blue-200/70">
                Inserts into SQL tables (<code className="text-cyan-300">vendors</code>,{' '}
                <code className="text-cyan-300">procurement_contracts</code>) and creates Knowledge Graph provenance edges.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                Indian Company Name *
              </label>
              <input
                type="text"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                placeholder="e.g., Wipro Limited, BHEL, Godrej Aerospace..."
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                City Hub (Select or Type Any City) *
              </label>
              <input
                type="text"
                list="indian-cities-list"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Gwalior, Jaipur, Mumbai, Morena, Bhopal..."
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none"
                required
              />
              <datalist id="indian-cities-list">
                {INDIAN_CITY_PRESETS.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>

            <div className="sm:col-span-2 space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                Primary Product / Domain *
              </label>
              <input
                type="text"
                value={primaryProduct}
                onChange={(e) => setPrimaryProduct(e.target.value)}
                placeholder="e.g., Smart Grid Transformers, Defence Avionics, Cloud AI Core..."
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none"
                required
              />
            </div>

            <div className="sm:col-span-2 space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                Connected Regional Facility (SUPPLIES_TO)
              </label>
              <select
                value={facilityId}
                onChange={(e) => setFacilityId(e.target.value)}
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none"
              >
                {FACILITY_OPTIONS.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                Contract Value (USD Equivalent)
              </label>
              <input
                type="number"
                value={contractValueUsd}
                onChange={(e) => setContractValueUsd(Number(e.target.value))}
                min={10000}
                step={50000}
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none font-mono"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                Compliance Score (0 - 100)
              </label>
              <input
                type="number"
                value={complianceScore}
                onChange={(e) => setComplianceScore(Number(e.target.value))}
                min={1}
                max={100}
                step={0.5}
                className="w-full px-4 py-3.5 rounded-xl bg-[#030d2b] border border-blue-400/35 text-base text-white focus:border-cyan-300 outline-none font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submittingCompany}
            className="btn-nexus w-full flex items-center justify-center gap-3 !py-4"
          >
            <PlusCircle className="w-5 h-5" />
            <span>
              {submittingCompany
                ? 'Adding to SQL Database & Knowledge Graph...'
                : 'Add Company to Database & Knowledge Graph'}
            </span>
          </button>

          {companyResult && (
            <div className="p-5 rounded-2xl bg-emerald-950/40 border border-emerald-400/40 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-mono text-emerald-300 font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  Added {companyResult.company_name} ({companyResult.vendor_id}) in {companyResult.city}
                </span>
                <span className="text-xs font-mono text-cyan-200">
                  Graph ID: {companyResult.entity_id}
                </span>
              </div>
              <button
                type="button"
                onClick={() =>
                  onAskAboutCompany(
                    `Show all vendor contracts and supply chain paths for ${companyResult.company_name}`
                  )
                }
                className="px-4 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-xs font-mono text-emerald-200 flex items-center gap-2 transition"
              >
                <Sparkles className="w-4 h-4" />
                <span>Verify {companyResult.company_name} in Ask Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </form>

        {/* Right 5 cols: Connect Any Two Knowledge Graph Entities */}
        <form
          onSubmit={handleAddRelationship}
          className="lg:col-span-5 rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-6 flex flex-col justify-between"
        >
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-blue-400/20 pb-4">
              <GitBranch className="w-6 h-6 text-violet-300" />
              <div>
                <h3 className="text-xl font-display font-bold text-white">
                  2. Connect Graph Nodes
                </h3>
                <p className="text-sm text-blue-200/70">
                  Add a custom relationship edge between any two Indian companies, cities, or facilities.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                  Source Entity (From)
                </label>
                <select
                  value={sourceEntityId}
                  onChange={(e) => setSourceEntityId(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white"
                >
                  {nodes.map((n) => (
                    <option key={`src-${n.id}`} value={n.id}>
                      {n.name} ({n.entity_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                  Relationship Type
                </label>
                <select
                  value={relType}
                  onChange={(e) => setRelType(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-cyan-200 font-mono"
                >
                  {[
                    'SUPPLIES_TO',
                    'LOCATED_IN',
                    'PART_OF',
                    'CONNECTED_TO',
                    'OWNS',
                    'MANAGES',
                    'WORKS_FOR',
                  ].map((rt) => (
                    <option key={rt} value={rt}>
                      {rt}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                  Target Entity (To)
                </label>
                <select
                  value={targetEntityId}
                  onChange={(e) => setTargetEntityId(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white"
                >
                  {nodes.map((n) => (
                    <option key={`tgt-${n.id}`} value={n.id}>
                      {n.name} ({n.entity_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-blue-200/80 block">
                  Provenance Note / Evidence Excerpt
                </label>
                <input
                  type="text"
                  value={relExcerpt}
                  onChange={(e) => setRelExcerpt(e.target.value)}
                  placeholder="e.g., Joint venture agreement signed in Gwalior..."
                  className="w-full px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white"
                />
              </div>
            </div>
          </div>

          <div className="space-y-4 pt-4">
            <button
              type="submit"
              className="btn-nexus-outline w-full flex items-center justify-center gap-2 !py-4"
            >
              <GitBranch className="w-4 h-4 text-cyan-300" />
              <span>Add Graph Relationship</span>
            </button>

            {relResult && (
              <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-400/40 text-xs font-mono text-emerald-300">
                Created relationship {relResult.relationship_id} in Knowledge Graph!
              </div>
            )}
          </div>
        </form>
      </div>

      {/* Live Roster of Indian Companies in SQL Database */}
      <div className="rounded-3xl glass-panel spotlight-card p-8 sm:p-10 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-blue-400/20 pb-4">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-cyan-300" />
            <div>
              <h3 className="text-xl font-display font-bold text-white">
                Active Indian Corporate Roster ({vendorsList.length} Records)
              </h3>
              <p className="text-sm text-blue-200/70">
                Live SQL records from <code className="text-cyan-300">enterprise_supply_ops.vendors</code>
              </p>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-blue-400/25 bg-[#030d2b]">
          <table className="w-full text-left border-collapse text-sm sm:text-base font-mono">
            <thead>
              <tr className="border-b border-blue-400/25 bg-blue-950/60 text-cyan-200">
                <th className="py-4 px-5">ID</th>
                <th className="py-4 px-5">Indian Company</th>
                <th className="py-4 px-5">City / Hub</th>
                <th className="py-4 px-5">Primary Product</th>
                <th className="py-4 px-5">Compliance</th>
                <th className="py-4 px-5">Total Contract Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-blue-400/15">
              {vendorsList.map((v, idx) => (
                <tr key={idx} className="hover:bg-blue-900/25 transition">
                  <td className="py-4 px-5 text-cyan-300">{v.vendor_id}</td>
                  <td className="py-4 px-5 text-white font-semibold">{v.vendor_name}</td>
                  <td className="py-4 px-5 text-blue-100">{v.country}</td>
                  <td className="py-4 px-5 text-slate-200">{v.primary_product}</td>
                  <td className="py-4 px-5 text-emerald-300">
                    {v.compliance_score ?? 'NULL'}
                  </td>
                  <td className="py-4 px-5 text-white tabular-nums">
                    ${Number(v.contract_usd || 0).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
