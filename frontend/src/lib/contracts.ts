import type {
  ContractClause,
  ContractDate,
  ContractRecord,
  GroupedClause,
  Lifecycle,
} from "./types";

const START_EVENTS = new Set(["Contract effective or commencement date"]);
const END_EVENT = "Contract expiration or end date";
const TERMINATION_EVENT = "Termination date";
const DEDICATED_EXTRACTOR_CATEGORIES = new Set(["Parties", "Expiration Date"]);

export function extractionConfidence(contract: ContractRecord): number | null {
  const scores = [
    ...contract.clauses.map((item) => item.confidence),
    ...contract.parties.map((item) => item.confidence),
    ...contract.dates.map((item) => item.confidence),
  ].filter((score): score is number => Number.isFinite(score));
  return scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null;
}

export function groupClauses(clauses: ContractClause[]): GroupedClause[] {
  const grouped = new Map<string, GroupedClause>();
  for (const clause of clauses) {
    if (DEDICATED_EXTRACTOR_CATEGORIES.has(clause.category)) continue;
    const key = clause.text.trim().replace(/\s+/g, " ");
    if (!key) continue;
    if (!grouped.has(key)) grouped.set(key, { text: clause.text, categories: [], clauseIds: [] });
    const group = grouped.get(key)!;
    group.clauseIds.push(clause.id);
    const category = group.categories.find((item) => item.name === clause.category);
    if (category) {
      category.confidence = Math.max(category.confidence, clause.confidence);
    } else {
      group.categories.push({ name: clause.category, confidence: clause.confidence });
    }
  }
  return [...grouped.values()];
}

function dateKey(value: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : null;
}

function todayInSingapore(): string {
  const parts = new Intl.DateTimeFormat("en-SG", {
    timeZone: "Asia/Singapore",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

type DatedContractDate = ContractDate & { key: string };

function sortedDates(items: ContractDate[]): DatedContractDate[] {
  return items.flatMap((item) => {
    const key = dateKey(item.date);
    return key ? [{ ...item, key }] : [];
  }).sort((a, b) => a.key.localeCompare(b.key));
}

export function lifecycle(contract: ContractRecord): Lifecycle {
  if (contract.status === "failed") return { status: "failed", label: "Failed", term: contract.error || "Processing failed" };
  const starts = sortedDates(contract.dates.filter((item) => START_EVENTS.has(item.event_desc)));
  const expirations = sortedDates(contract.dates.filter((item) => item.event_desc === END_EVENT));
  const terminations = sortedDates(contract.dates.filter((item) => item.event_desc === TERMINATION_EVENT));
  const start = starts.at(0) || null;
  const end = terminations.at(0) || expirations.at(-1) || null;
  const display = (item: DatedContractDate | null, fallback: string) => item ? `${item.date}${item.provenance === "derived" ? " (derived)" : ""}` : fallback;
  const term = `${display(start, "Start not identified")} — ${display(end, "End not identified")}`;
  if (!start && !end) return { status: "undated", label: "Dates unavailable", term };
  if (start && end && start.key > end.key) return { status: "review", label: "Review dates", term };
  const today = todayInSingapore();
  if (start && today < start.key) return { status: "upcoming", label: "Upcoming", term };
  if (end && today > end.key) return { status: "expired", label: "Expired", term };
  return { status: "active", label: "Active", term };
}
