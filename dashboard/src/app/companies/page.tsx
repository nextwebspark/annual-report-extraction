import { getAllCompaniesWithFactsAsync } from "@/lib/db";
import { getNormalizedRevenue, getConfidence } from "@/lib/json-helpers";
import CompanyTable from "@/components/CompanyTable";

export const dynamic = "force-dynamic";

export default async function CompaniesPage() {
  const companies = await getAllCompaniesWithFactsAsync();

  const rows = companies.map((c) => {
    const confidences = [
      c.company_name,
      c.exchange,
      c.country,
      c.industry,
      c.revenue,
      c.profit_net,
    ].map((f) => getConfidence(f));
    const avgConf =
      confidences.reduce((a, b) => a + b, 0) / confidences.length;

    return {
      id: c.id,
      name: c.company_name?.value ?? "Unknown",
      industry: c.industry?.value ?? "Unknown",
      country: c.country?.value ?? "Unknown",
      exchange: c.exchange?.value ?? "Unknown",
      year: c.year,
      revenue: getNormalizedRevenue(c.revenue),
      profit: getNormalizedRevenue(c.profit_net),
      marketCap: getNormalizedRevenue(c.market_capitalisation),
      employees: c.employees?.value ?? null,
      avgConfidence: avgConf,
      currency: c.revenue?.currency ?? "SAR",
    };
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Companies</h1>
      <CompanyTable data={rows} />
    </div>
  );
}
