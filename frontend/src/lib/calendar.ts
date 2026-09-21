import type { CalendarEvent, DateProvenance } from "./types";

type CalendarEventDraft = Partial<CalendarEvent>;

function unescapeCalendarValue(value: string): string {
  return value.replace(/\\([\\,;nN])/g, (_match: string, escaped: string) => escaped.toLowerCase() === "n" ? "\n" : escaped);
}

export function parseCalendar(content: string): CalendarEvent[] {
  const lines = content.replace(/\r?\n[ \t]/g, "").split(/\r?\n/);
  const events: CalendarEvent[] = [];
  let event: CalendarEventDraft | null = null;
  for (const line of lines) {
    if (line === "BEGIN:VEVENT") { event = {}; continue; }
    if (line === "END:VEVENT") {
      if (event?.date && event.summary) {
        events.push({
          id: event.id || `${event.date}-${event.summary}`,
          date: event.date,
          summary: event.summary,
          source: event.source || "Contract",
          confidence: event.confidence ?? 0,
          provenance: event.provenance || "explicit",
          contractId: event.contractId,
          evidence: event.evidence,
          startOffset: event.startOffset,
          endOffset: event.endOffset,
        });
      }
      event = null;
      continue;
    }
    if (!event) continue;
    const separator = line.indexOf(":");
    if (separator < 0) continue;
    const property = line.slice(0, separator).split(";", 1)[0];
    const value = unescapeCalendarValue(line.slice(separator + 1));
    if (property === "UID") event.id = value.replace(/@eagle-eye\.local$/, "");
    if (property === "DTSTART" && /^\d{8}$/.test(value)) event.date = `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
    if (property === "SUMMARY") event.summary = value;
    if (property === "X-EAGLEEYE-CONTRACT-ID") event.contractId = value;
    if (property === "X-EAGLEEYE-SOURCE") event.source = value;
    if (property === "X-EAGLEEYE-EVENT-DESC") event.summary = value;
    if (property === "X-EAGLEEYE-CONFIDENCE") event.confidence = Number.parseFloat(value);
    if (property === "X-EAGLEEYE-PROVENANCE") event.provenance = value as DateProvenance;
    if (property === "X-EAGLEEYE-EVIDENCE") event.evidence = value;
    if (property === "X-EAGLEEYE-START-OFFSET") event.startOffset = Number.parseInt(value, 10);
    if (property === "X-EAGLEEYE-END-OFFSET") event.endOffset = Number.parseInt(value, 10);
  }
  return events.sort((a, b) => a.date.localeCompare(b.date) || a.summary.localeCompare(b.summary));
}

export function localDateKey(date: Date): string {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}
