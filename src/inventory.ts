/**
 * Build the South America accelerator inventory.
 *
 * Pulls every investor of type `accelerator` head-quartered on the South America
 * continent (Dealroom location id 74) and writes a compact record per accelerator
 * to data/accelerators.json, plus a per-country summary to data/summary.json.
 *
 * This is the region-wide foundation for both goals:
 *   - coverage sampling (portfolio size + website to scrape)
 *   - cadence prioritisation (activity/recency signals)
 *
 * Run: npm run inventory
 */

import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { dealroom } from "./dealroom.js";

const SOUTH_AMERICA_LOCATION_ID = 74; // continent/south-america
const PAGE_SIZE = 50;
const DATA_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "data");

/** A raw investor record from /api/data/investors (only the fields we read). */
interface RawInvestor {
  uuid: string;
  name: string;
  tagline: string | null;
  website: string | null;
  website_domain: string | null;
  dealroom_url: string | null;
  linkedin_url: string | null;
  hq_country: string | null;
  hq_city: string | null;
  founding_country: string | null;
  launch_year: number | null;
  employee_count: number | null;
  investor_rank: number | null;
  investments?: {
    total_count?: number | null;
    total_invested?: number | null;
    preferred_round?: string | null;
    last_investor_round_year?: number | null;
    last_investor_round_month?: number | null;
  } | null;
  portfolio?: {
    companies?: number | null;
    total_rounds?: number | null;
  } | null;
}

/** The compact record we persist for each accelerator. */
interface Accelerator {
  uuid: string;
  name: string;
  tagline: string | null;
  country: string | null;
  city: string | null;
  website: string | null;
  website_domain: string | null;
  dealroom_url: string | null;
  linkedin_url: string | null;
  launch_year: number | null;
  employee_count: number | null;
  investor_rank: number | null;
  portfolio_companies: number | null;
  total_rounds: number | null;
  investments_total_count: number | null;
  total_invested: number | null;
  preferred_round: string | null;
  last_round_year: number | null;
  last_round_month: number | null;
}

function toAccelerator(r: RawInvestor): Accelerator {
  return {
    uuid: r.uuid,
    name: r.name,
    tagline: r.tagline ?? null,
    country: r.hq_country ?? r.founding_country ?? null,
    city: r.hq_city ?? null,
    website: r.website ?? null,
    website_domain: r.website_domain ?? null,
    dealroom_url: r.dealroom_url ?? null,
    linkedin_url: r.linkedin_url ?? null,
    launch_year: r.launch_year ?? null,
    employee_count: r.employee_count ?? null,
    investor_rank: r.investor_rank ?? null,
    portfolio_companies: r.portfolio?.companies ?? null,
    total_rounds: r.portfolio?.total_rounds ?? null,
    investments_total_count: r.investments?.total_count ?? null,
    total_invested: r.investments?.total_invested ?? null,
    preferred_round: r.investments?.preferred_round ?? null,
    last_round_year: r.investments?.last_investor_round_year ?? null,
    last_round_month: r.investments?.last_investor_round_month ?? null,
  };
}

async function fetchPage(offset: number): Promise<{ data: RawInvestor[]; total: number }> {
  const { data } = await dealroom.get("/data/investors", {
    params: {
      filter: `and(investor_type[eq]:accelerator,hq_location[eq]:${SOUTH_AMERICA_LOCATION_ID})`,
      limit: PAGE_SIZE,
      offset,
      include_total: true,
      sort: "-investor_rank",
    },
  });
  return { data: data.data ?? [], total: data.page?.total ?? 0 };
}

async function main() {
  console.log("Fetching South America accelerators from Dealroom…");
  const all: Accelerator[] = [];
  let offset = 0;
  let total = Infinity;

  while (offset < total) {
    const { data, total: pageTotal } = await fetchPage(offset);
    total = pageTotal;
    if (data.length === 0) break;
    all.push(...data.map(toAccelerator));
    console.log(`  …${all.length}/${total}`);
    offset += PAGE_SIZE;
  }

  // Sort by portfolio size (largest first) for a readable file.
  all.sort((a, b) => (b.portfolio_companies ?? 0) - (a.portfolio_companies ?? 0));

  // Per-country summary.
  const byCountry: Record<string, { accelerators: number; portfolio_companies: number }> = {};
  for (const a of all) {
    const c = a.country ?? "Unknown";
    byCountry[c] ??= { accelerators: 0, portfolio_companies: 0 };
    byCountry[c].accelerators += 1;
    byCountry[c].portfolio_companies += a.portfolio_companies ?? 0;
  }
  const summary = {
    generated_at: new Date().toISOString(),
    total_accelerators: all.length,
    total_portfolio_companies: all.reduce((s, a) => s + (a.portfolio_companies ?? 0), 0),
    with_website: all.filter((a) => a.website).length,
    by_country: Object.fromEntries(
      Object.entries(byCountry).sort((a, b) => b[1].accelerators - a[1].accelerators),
    ),
  };

  writeFileSync(join(DATA_DIR, "accelerators.json"), JSON.stringify(all, null, 2));
  writeFileSync(join(DATA_DIR, "summary.json"), JSON.stringify(summary, null, 2));

  console.log(`\nWrote ${all.length} accelerators to data/accelerators.json`);
  console.log("Summary by country:");
  for (const [country, s] of Object.entries(summary.by_country)) {
    console.log(`  ${country.padEnd(20)} ${String(s.accelerators).padStart(3)} accelerators, ${s.portfolio_companies} portfolio companies`);
  }
  console.log(`\n${summary.with_website}/${all.length} have a website (scrapeable for coverage).`);
}

main().catch((err) => {
  console.error("Inventory failed:", err?.response?.data ?? err?.message ?? err);
  process.exit(1);
});
