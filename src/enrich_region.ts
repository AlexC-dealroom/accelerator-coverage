/**
 * Enrich a region's accelerator frame from the Dealroom beta API, per-UUID.
 *
 * The trustworthy country/state FRAME comes from the platform (Dealroom MCP
 * search_investors) — the beta investor SEARCH undercounts. But the missing
 * accelerators DO exist in beta by UUID, so we enrich each one individually:
 *   GET /data/investors/{uuid}            -> website, domain, dealroom_url, last round
 *   GET /data/investors/{uuid}/portfolio  -> portfolio count (cursor-paged; count it)
 *
 * Reads:  data/<region>_frame.json     [{uuid, name, city}, ...]
 * Writes: data/<region>_accelerators.json   (same shape as brazil_accelerators.json)
 *
 * Run:  npx tsx src/enrich_region.ts <region>
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { dealroom } from "./dealroom.js";

const DATA_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "data");

const region = process.argv[2];
if (!region) {
  console.error("Usage: npx tsx src/enrich_region.ts <region>   (e.g. colorado)");
  process.exit(1);
}

interface Seed { uuid: string; name: string; city?: string | null; }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** GET with retry/backoff on 429 (rate limit) and transient 5xx. */
async function getWithRetry(url: string, params?: Record<string, unknown>): Promise<any> {
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      const { data } = await dealroom.get(url, params ? { params } : undefined);
      return data;
    } catch (e: any) {
      const status = e?.response?.status;
      if ((status === 429 || (status >= 500 && status < 600)) && attempt < 5) {
        await sleep(1500 * (attempt + 1));
        continue;
      }
      throw e;
    }
  }
}

async function getInvestor(uuid: string): Promise<any | null> {
  try {
    const data = await getWithRetry(`/data/investors/${uuid}`);
    return data?.data ?? data ?? null;
  } catch (e: any) {
    console.error(`  ! investor ${uuid}: ${e?.response?.status ?? e?.message}`);
    return null;
  }
}

/** Count portfolio companies by walking the offset-paged sub-resource. */
async function portfolioCount(uuid: string): Promise<number | null> {
  const LIMIT = 100;
  let total = 0;
  for (let offset = 0; offset < 20000; offset += LIMIT) {
    try {
      const data = await getWithRetry(`/data/investors/${uuid}/portfolio`, { limit: LIMIT, offset });
      const items = data?.data ?? [];
      total += items.length;
      if (items.length < LIMIT) return total;
    } catch (e: any) {
      console.error(`  ! portfolio ${uuid}: ${e?.response?.status ?? e?.message}`);
      return total || null;
    }
  }
  return total;
}

function domainOf(website: string | null | undefined, fallback: string | null | undefined): string | null {
  if (fallback) return fallback;
  if (!website) return null;
  try { return new URL(website.startsWith("http") ? website : `https://${website}`).hostname.replace(/^www\./, ""); }
  catch { return null; }
}

async function main() {
  const seeds: Seed[] = JSON.parse(readFileSync(join(DATA_DIR, `${region}_frame.json`), "utf8"));
  console.log(`Enriching ${seeds.length} ${region} accelerators from beta…`);
  const out: any[] = [];
  for (const s of seeds) {
    const inv = await getInvestor(s.uuid);
    const pf = await portfolioCount(s.uuid);
    const website = inv?.website ?? null;
    out.push({
      uuid: s.uuid,
      name: s.name ?? inv?.name ?? null,
      city: s.city ?? inv?.hq_city ?? null,
      website,
      domain: domainOf(website, inv?.website_domain),
      hq_country: inv?.hq_country ?? "United States",
      dealroom_portfolio: pf,
      last_round_year: inv?.investments?.last_investor_round_year ?? null,
      investor_types: (inv?.investor_types ?? []).map((t: any) => (typeof t === "string" ? t : t?.name)).filter(Boolean),
      dealroom_url: inv?.dealroom_url ?? null,
    });
    console.log(`  ${s.name.padEnd(42)} pf=${pf ?? "?"}  ${website ?? "(no website)"}`);
    await sleep(300);
  }
  writeFileSync(join(DATA_DIR, `${region}_accelerators.json`), JSON.stringify(out, null, 2));
  console.log(`\nWrote data/${region}_accelerators.json (${out.length} accelerators)`);
}

main().catch((err) => {
  console.error("Enrichment failed:", err?.response?.data ?? err?.message ?? err);
  process.exit(1);
});
