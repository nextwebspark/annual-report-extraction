import { getSummaryStatsAsync, getAllCompaniesWithFactsAsync } from "@/lib/db";
import { getNormalizedRevenue, formatCompact, confidenceBg } from "@/lib/json-helpers";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const stats = await getSummaryStatsAsync();
  const companies = await getAllCompaniesWithFactsAsync();

  const cards = [
    { label: "Companies", value: stats.totalCompanies, color: "bg-blue-500/20 text-blue-400" },
    { label: "Directors", value: stats.totalDirectors, color: "bg-emerald-500/20 text-emerald-400" },
    { label: "Committee Members", value: stats.totalCommittees, color: "bg-violet-500/20 text-violet-400" },
    {
      label: "Avg Confidence",
      value: `${(stats.avgConfidence * 100).toFixed(0)}%`,
      color: confidenceBg(stats.avgConfidence),
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card) => (
          <div
            key={card.label}
            className="bg-slate-900 border border-slate-800 rounded-xl p-5"
          >
            <p className="text-sm text-slate-400 mb-1">{card.label}</p>
            <p className={`text-3xl font-bold ${card.color.split(" ")[1]}`}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold">Companies</h2>
          <Link
            href="/companies"
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            View all →
          </Link>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-800">
              <th className="px-5 py-3 font-medium">Company</th>
              <th className="px-5 py-3 font-medium">Year</th>
              <th className="px-5 py-3 font-medium text-right">Revenue</th>
              <th className="px-5 py-3 font-medium text-right">Net Profit</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => {
              const rev = getNormalizedRevenue(c.revenue);
              const profit = getNormalizedRevenue(c.profit_net);
              return (
                <tr
                  key={c.id}
                  className="border-b border-slate-800/50 hover:bg-slate-800/30"
                >
                  <td className="px-5 py-3">
                    <Link
                      href={`/companies/${c.id}`}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      {c.company_name?.value ?? "Unknown"}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-slate-400">{c.year ?? "-"}</td>
                  <td className="px-5 py-3 text-right font-mono">
                    {rev != null ? `SAR ${formatCompact(rev)}` : "N/A"}
                  </td>
                  <td
                    className={`px-5 py-3 text-right font-mono ${
                      profit != null && profit < 0 ? "text-red-400" : ""
                    }`}
                  >
                    {profit != null ? `SAR ${formatCompact(profit)}` : "N/A"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
