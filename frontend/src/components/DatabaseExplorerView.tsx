import React, { useState, useEffect } from 'react';
import {
  Database,
  ShieldCheck,
  Table,
  Play,
  Wrench,
  Terminal,
} from 'lucide-react';
import { api, SQLExecuteResponse } from '../api';

interface DatabaseExplorerViewProps {
  activeSourceId: string;
  onSourceChange: (sourceId: string) => void;
}

export const DatabaseExplorerView: React.FC<DatabaseExplorerViewProps> = ({
  activeSourceId,
  onSourceChange,
}) => {
  const [schema, setSchema] = useState<any>(null);
  const [selectedTable, setSelectedTable] = useState<any>(null);
  const [sqlInput, setSqlInput] = useState<string>(
    'SELECT r.region_name, COUNT(f.facility_id) AS facilities, SUM(f.annual_budget_usd) AS total_budget_usd FROM regions r JOIN facilities f ON r.region_id = f.region_id GROUP BY r.region_name ORDER BY total_budget_usd DESC'
  );
  const [execRes, setExecRes] = useState<SQLExecuteResponse | null>(null);

  const loadSchema = async (srcId: string) => {
    const sc = await api.getSchema(srcId);
    setSchema(sc);
    if (sc.tables && sc.tables.length > 0) {
      setSelectedTable(sc.tables[0]);
    }
  };

  useEffect(() => {
    loadSchema(activeSourceId);
    if (activeSourceId === 'california_schools_bird_demo') {
      setSqlInput(
        'SELECT s.School, s.City, s.Region, sat.AvgScrMath, f.EligibleFreeRate_K12 FROM schools s JOIN satscores sat ON s.CDSCode = sat.cds JOIN frpm f ON s.CDSCode = f.CDSCode ORDER BY sat.AvgScrMath DESC'
      );
    } else {
      setSqlInput(
        'SELECT r.region_name, COUNT(f.facility_id) AS facilities, SUM(f.annual_budget_usd) AS total_budget_usd FROM regions r JOIN facilities f ON r.region_id = f.region_id GROUP BY r.region_name ORDER BY total_budget_usd DESC'
      );
    }
    setExecRes(null);
  }, [activeSourceId]);

  const handleExecuteSql = async () => {
    const res = await api.executeSql(activeSourceId, sqlInput, 'SQL Workbench Execution', true);
    setExecRes(res);
  };

  return (
    <div className="space-y-10">
      {/* Clean Header */}
      <div className="rounded-3xl glass-panel-elevated p-8 flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="eye-label">READ-ONLY SQLITE ENGINE</span>
            <span className="px-3 py-0.5 rounded-full text-xs font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/35 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              Protected Read-Only
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-display font-bold text-white">
            Database Tables & Safe SQL Workbench
          </h2>
          <p className="text-base text-blue-100/75 font-light">{schema?.description}</p>
        </div>

        <select
          value={activeSourceId}
          onChange={(e) => onSourceChange(e.target.value)}
          className="px-4 py-3 rounded-xl bg-[#030d2b] border border-blue-400/35 text-sm text-white font-mono"
        >
          <option value="enterprise_supply_ops">Indian Corporate Supply DB</option>
          <option value="california_schools_bird_demo">Regional STEM Schools (BIRD)</option>
        </select>
      </div>

      {/* Table Selector & Live Row Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left 4 cols: Tables List */}
        <div className="lg:col-span-4 rounded-3xl glass-panel p-6 space-y-4">
          <h3 className="text-sm font-mono uppercase tracking-wider text-cyan-200 flex items-center gap-2">
            <Table className="w-4 h-4 text-cyan-400" />
            Database Tables ({schema?.tables?.length || 0})
          </h3>
          <div className="space-y-3">
            {(schema?.tables || []).map((tbl: any) => {
              const isSelected = selectedTable?.table_name === tbl.table_name;
              return (
                <button
                  key={tbl.table_name}
                  type="button"
                  onClick={() => setSelectedTable(tbl)}
                  className={`w-full text-left p-4 rounded-2xl border transition flex items-center justify-between ${
                    isSelected
                      ? 'bg-blue-600/30 border-cyan-300/70 text-white'
                      : 'bg-[#030d2b] border-blue-400/20 text-slate-300 hover:border-blue-400/40'
                  }`}
                >
                  <div>
                    <div className="font-mono text-sm font-bold">{tbl.table_name}</div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {tbl.columns?.length} columns
                    </div>
                  </div>
                  <span className="font-mono text-sm text-cyan-300">{tbl.row_count} rows</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right 8 cols: Selected Table Data */}
        <div className="lg:col-span-8 rounded-3xl glass-panel p-8 space-y-6">
          {selectedTable && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-400/20 pb-4">
                <div>
                  <h3 className="text-xl font-display font-bold text-white font-mono">
                    {selectedTable.table_name}
                  </h3>
                  <p className="text-sm text-blue-200/70 mt-0.5">
                    Showing live records from {selectedTable.table_name}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSqlInput(`SELECT * FROM ${selectedTable.table_name} LIMIT 25`)}
                  className="px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/40 text-xs font-mono"
                >
                  Query This Table
                </button>
              </div>

              <div className="overflow-x-auto rounded-2xl border border-blue-400/25 bg-[#030d2b]">
                <table className="w-full text-left border-collapse text-sm font-mono">
                  <thead>
                    <tr className="border-b border-blue-400/25 bg-blue-950/60 text-cyan-200">
                      {selectedTable.columns.map((c: any) => (
                        <th key={c.name} className="py-3.5 px-4 whitespace-nowrap">
                          {c.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-blue-400/15">
                    {(selectedTable.sample_rows || []).map((row: any, rIdx: number) => (
                      <tr key={rIdx} className="hover:bg-blue-900/20">
                        {selectedTable.columns.map((c: any) => {
                          const val = row[c.name];
                          return (
                            <td key={c.name} className="py-3.5 px-4 whitespace-nowrap text-slate-100">
                              {val === null || val === undefined ? (
                                <span className="text-rose-300">NULL</span>
                              ) : (
                                String(val)
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Simple, Straight-to-the-Point SQL Execution & Guardrail Tester */}
      <div className="rounded-3xl glass-panel-elevated p-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Terminal className="w-6 h-6 text-cyan-300" />
            <div>
              <h3 className="text-xl font-display font-bold text-white">
                Safe SQL Execution & Auto-Repair Sandbox
              </h3>
              <p className="text-sm text-blue-200/70">
                Run any read-only SELECT query, or test automatic column repair and destructive SQL blocking.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                setSqlInput(
                  'SELECT v.vendor_name, c.contract_amount FROM procurement_contracts c JOIN vendors v ON c.vendor_id = v.vendor_id'
                )
              }
              className="px-3.5 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-200 border border-amber-400/35 text-xs font-mono"
            >
              Test Auto-Repair
            </button>
            <button
              type="button"
              onClick={() => setSqlInput('DROP TABLE vendors;')}
              className="px-3.5 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 border border-rose-400/35 text-xs font-mono"
            >
              Test Security Block
            </button>
          </div>
        </div>

        <textarea
          rows={3}
          value={sqlInput}
          onChange={(e) => setSqlInput(e.target.value)}
          className="w-full p-5 rounded-2xl bg-[#030d2b] border border-blue-400/35 font-mono text-sm text-cyan-200 focus:border-cyan-300 outline-none"
        />

        <button
          type="button"
          onClick={handleExecuteSql}
          className="btn-nexus flex items-center gap-2.5 !py-3.5 !px-7"
        >
          <Play className="w-4 h-4" />
          <span>Execute Read-Only SQL</span>
        </button>

        {execRes && (
          <div className="space-y-4 pt-4 border-t border-blue-400/20">
            {execRes.repair_attempts?.length > 0 && (
              <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-400/40 text-sm font-mono text-amber-200 flex items-center gap-3">
                <Wrench className="w-5 h-5 shrink-0" />
                <span>Auto-Repaired Column: {execRes.repair_attempts[0].repair_reason}</span>
              </div>
            )}

            {execRes.execution_success ? (
              <div className="overflow-x-auto rounded-2xl border border-blue-400/25 bg-[#030d2b] max-h-72">
                <table className="w-full text-left border-collapse text-sm font-mono">
                  <thead>
                    <tr className="border-b border-blue-400/25 bg-blue-950/60 text-cyan-200">
                      {execRes.columns.map((c) => (
                        <th key={c} className="py-3.5 px-4">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-blue-400/15">
                    {execRes.rows.map((r, i) => (
                      <tr key={i}>
                        {execRes.columns.map((c) => (
                          <td key={c} className="py-3.5 px-4 text-slate-100">
                            {r[c] === null ? 'NULL' : String(r[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-5 rounded-2xl bg-rose-950/35 border border-rose-500/40 text-sm font-mono text-rose-200">
                Blocked by Read-Only Authorizer: {execRes.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
