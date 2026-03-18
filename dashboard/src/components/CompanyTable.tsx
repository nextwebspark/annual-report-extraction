"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { formatCompact, confidenceBg } from "@/lib/json-helpers";

interface CompanyRow {
  id: number;
  name: string;
  industry: string;
  country: string;
  exchange: string;
  year: number | null;
  revenue: number | null;
  profit: number | null;
  marketCap: number | null;
  employees: number | null;
  avgConfidence: number;
  currency: string;
}

type SortKey = keyof CompanyRow;

export default function CompanyTable({ data }: { data: CompanyRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return data.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.industry.toLowerCase().includes(q) ||
        c.country.toLowerCase().includes(q)
    );
  }, [data, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === "string" ? av.localeCompare(bv as string) : (av as number) - (bv as number);
      return sortAsc ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "name");
    }
  }

  const headers: { key: SortKey; label: string; align?: string }[] = [
    { key: "name", label: "Company" },
    { key: "industry", label: "Industry" },
    { key: "year", label: "Year" },
    { key: "revenue", label: "Revenue", align: "text-right" },
    { key: "profit", label: "Net Profit", align: "text-right" },
    { key: "marketCap", label: "Market Cap", align: "text-right" },
    { key: "employees", label: "Employees", align: "text-right" },
    { key: "avgConfidence", label: "Confidence" },
  ];

  return (
    <div>
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 w-full max-w-sm"
        />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-800">
                {headers.map((h) => (
                  <th
                    key={h.key}
                    onClick={() => toggleSort(h.key)}
                    className={`px-4 py-3 font-medium cursor-pointer hover:text-white transition-colors select-none ${h.align ?? ""}`}
                  >
                    {h.label}
                    {sortKey === h.key && (
                      <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/companies/${c.id}`}
                      className="text-blue-400 hover:text-blue-300 font-medium"
                    >
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{c.industry}</td>
                  <td className="px-4 py-3 text-slate-400">{c.year ?? "-"}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {c.revenue != null
                      ? `${c.currency} ${formatCompact(c.revenue)}`
                      : "N/A"}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-mono ${
                      c.profit != null && c.profit < 0 ? "text-red-400" : ""
                    }`}
                  >
                    {c.profit != null
                      ? `${c.currency} ${formatCompact(c.profit)}`
                      : "N/A"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {c.marketCap != null
                      ? `${c.currency} ${formatCompact(c.marketCap)}`
                      : "N/A"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {c.employees != null
                      ? c.employees.toLocaleString()
                      : "N/A"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${confidenceBg(
                        c.avgConfidence
                      )}`}
                    >
                      {(c.avgConfidence * 100).toFixed(0)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
