import {
  getCompanyByIdAsync,
  getDirectorsByFactIdAsync,
  getCommitteesByFactIdAsync,
} from "@/lib/db";
import {
  getNormalizedRevenue,
  formatCurrency,
  confidenceBg,
  getConfidence,
} from "@/lib/json-helpers";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function CompanyDetailPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyByIdAsync(Number(companyId));

  if (!company) {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold text-slate-400">Company not found</h1>
        <Link href="/companies" className="text-blue-400 mt-4 inline-block">
          ← Back to companies
        </Link>
      </div>
    );
  }

  const directors = company.fact_id
    ? await getDirectorsByFactIdAsync(company.fact_id)
    : [];
  const committees = company.fact_id
    ? await getCommitteesByFactIdAsync(company.fact_id)
    : [];

  const rev = getNormalizedRevenue(company.revenue);
  const profit = getNormalizedRevenue(company.profit_net);
  const marketCap = getNormalizedRevenue(company.market_capitalisation);
  const currency = company.revenue?.currency ?? "SAR";

  // Group committees by committee_name
  const committeeGroups: Record<string, typeof committees> = {};
  for (const cm of committees) {
    const name = cm.committee_name || "Other";
    if (!committeeGroups[name]) committeeGroups[name] = [];
    committeeGroups[name].push(cm);
  }

  return (
    <div>
      <Link
        href="/companies"
        className="text-sm text-slate-400 hover:text-white mb-4 inline-block"
      >
        ← Back to companies
      </Link>

      <h1 className="text-2xl font-bold mb-1">
        {company.company_name?.value ?? "Unknown"}
      </h1>
      <div className="flex gap-3 text-sm text-slate-400 mb-6">
        <span>{company.exchange?.value}</span>
        <span>·</span>
        <span>{company.country?.value}</span>
        <span>·</span>
        <span>{company.industry?.value}</span>
        {company.year && (
          <>
            <span>·</span>
            <span>FY {company.year}</span>
          </>
        )}
      </div>

      {/* Financials */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Revenue", value: rev, field: company.revenue },
          { label: "Net Profit", value: profit, field: company.profit_net },
          {
            label: "Market Cap",
            value: marketCap,
            field: company.market_capitalisation,
          },
          {
            label: "Employees",
            value: company.employees?.value,
            field: company.employees,
            isCurrency: false,
          },
        ].map((item) => (
          <div
            key={item.label}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4"
          >
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm text-slate-400">{item.label}</p>
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${confidenceBg(
                  getConfidence(item.field)
                )}`}
              >
                {(getConfidence(item.field) * 100).toFixed(0)}%
              </span>
            </div>
            <p
              className={`text-xl font-bold ${
                item.value != null && (item.value as number) < 0
                  ? "text-red-400"
                  : "text-white"
              }`}
            >
              {item.value != null
                ? item.isCurrency === false
                  ? (item.value as number).toLocaleString()
                  : formatCurrency(item.value as number, currency)
                : "N/A"}
            </p>
            {item.field?.source && (
              <p className="text-xs text-slate-500 mt-1 truncate">
                {item.field.source}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Directors */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mb-8">
        <div className="px-5 py-4 border-b border-slate-800">
          <h2 className="font-semibold">
            Board of Directors ({directors.length})
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-800">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Nationality</th>
                <th className="px-4 py-3 font-medium">Gender</th>
                <th className="px-4 py-3 font-medium text-right">Meetings</th>
                <th className="px-4 py-3 font-medium text-right">
                  Retainer Fee
                </th>
                <th className="px-4 py-3 font-medium text-right">
                  Attendance
                </th>
                <th className="px-4 py-3 font-medium text-right">
                  Committee Fee
                </th>
                <th className="px-4 py-3 font-medium text-right">
                  Total Fee
                </th>
              </tr>
            </thead>
            <tbody>
              {directors.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-slate-800/50 hover:bg-slate-800/30"
                >
                  <td className="px-4 py-3 font-medium">{d.director_name}</td>
                  <td className="px-4 py-3 text-slate-400">{d.board_role}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {d.director_type}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{d.nationality}</td>
                  <td className="px-4 py-3 text-slate-400">{d.gender}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {d.board_meetings_attended}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(d.retainer_fee, currency)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(d.attendance_allowance, currency)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(
                      d.director_board_committee_fee,
                      currency
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {formatCurrency(d.total_fee, currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Committees */}
      {Object.entries(committeeGroups).map(([name, members]) => (
        <div
          key={name}
          className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mb-4"
        >
          <div className="px-5 py-4 border-b border-slate-800">
            <h2 className="font-semibold">
              {name} ({members.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-800">
                  <th className="px-4 py-3 font-medium">Member</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Nationality</th>
                  <th className="px-4 py-3 font-medium text-right">
                    Meetings
                  </th>
                  <th className="px-4 py-3 font-medium text-right">
                    Retainer Fee
                  </th>
                  <th className="px-4 py-3 font-medium text-right">
                    Allowances
                  </th>
                  <th className="px-4 py-3 font-medium text-right">
                    Total Fee
                  </th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr
                    key={m.id}
                    className="border-b border-slate-800/50 hover:bg-slate-800/30"
                  >
                    <td className="px-4 py-3 font-medium">{m.member_name}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {m.committee_role}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {m.nationality}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {m.committee_meetings_attended}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {formatCurrency(m.committee_retainer_fee, currency)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {formatCurrency(m.committee_allowances, currency)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold">
                      {formatCurrency(m.committee_total_fee, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
