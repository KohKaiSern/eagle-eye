import type {
  ContractRecord,
  ConflictsResponse,
  ContractsResponse,
  SearchResponse,
  UploadEntry,
  UploadResponse,
} from "./types";

interface ErrorResponse {
  detail?: string;
}

async function jsonRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const body: unknown = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? (body as ErrorResponse).detail
      : undefined;
    throw new Error(detail || "The request failed.");
  }
  return body as T;
}

export const fetchContracts = (): Promise<ContractsResponse> => jsonRequest("/api/contracts");
export const fetchConflicts = (): Promise<ConflictsResponse> => jsonRequest("/api/conflicts");
export const fetchContract = (id: string): Promise<ContractRecord> => jsonRequest(`/api/contracts/${encodeURIComponent(id)}`);
export const searchContracts = (query: string): Promise<SearchResponse> => jsonRequest(`/api/contracts/search?q=${encodeURIComponent(query)}&limit=24`);
export const deleteContract = (id: string): Promise<void> => jsonRequest(`/api/contracts/${encodeURIComponent(id)}`, { method: "DELETE" });

export async function uploadContracts(entries: UploadEntry[]): Promise<UploadResponse> {
  const body = new FormData();
  for (const entry of entries) {
    body.append("files", entry.file, entry.file.name);
    body.append("paths", entry.path);
  }
  return jsonRequest("/api/contracts/upload", { method: "POST", body });
}

export async function fetchCalendar(): Promise<string> {
  const response = await fetch("/api/calendar.ics", { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load the contract calendar.");
  return response.text();
}
