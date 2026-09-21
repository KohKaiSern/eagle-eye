<script lang="ts">
  import { searchContracts } from "../../lib/api";
  import type { SearchMatch } from "../../lib/types";

  interface Props {
    onError: (message: string) => void;
  }

  let { onError }: Props = $props();
  let query = $state("");
  let matches = $state<SearchMatch[]>([]);
  let status = $state("");
  let open = $state(false);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  function updateQuery(event: Event): void {
    query = (event.currentTarget as HTMLInputElement).value;
    clearTimeout(searchTimer);
    const value = query.trim();
    if (value.length < 2) {
      matches = [];
      status = value ? "Type at least 2 characters" : "";
      open = Boolean(value);
      return;
    }
    searchTimer = setTimeout(() => runSearch(value), 280);
  }

  function clearSearch(): void {
    clearTimeout(searchTimer);
    query = "";
    matches = [];
    status = "";
    open = false;
  }

  async function runSearch(value: string): Promise<void> {
    status = "Searching…";
    open = true;
    try {
      const result = await searchContracts(value);
      if (query.trim() !== result.query) return;
      matches = result.matches;
      status = matches.length ? `${matches.length} close match${matches.length === 1 ? "" : "es"}` : "No close matches";
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : "Could not search contract text.");
    }
  }

  function closeFromOutside(event: PointerEvent): void {
    if (!(event.target instanceof Element) || !event.target.closest("[data-contract-search]")) open = false;
  }
</script>

<div class="relative w-full max-w-lg" data-contract-search>
  <label class="flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-3 shadow-sm transition focus-within:border-brand-500 focus-within:ring-3 focus-within:ring-brand-100">
    <svg class="h-4 w-4 shrink-0 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
    <span class="sr-only">Search contract text</span>
    <input value={query} oninput={updateQuery} onfocus={() => query && (open = true)} class="min-w-0 flex-1 bg-transparent text-sm outline-none" placeholder="Search contract text…" />
    {#if query}<button type="button" class="text-lg leading-none text-slate-400 hover:text-slate-700" onclick={clearSearch} aria-label="Clear search">×</button>{/if}
  </label>

  {#if open}
    <div class="absolute right-0 z-40 mt-2 max-h-[28rem] w-full min-w-80 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-200/70">
      <p class="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{status}</p>
      {#each matches as match}
        <a href={`/contracts/${match.contract_id}/text?start=${match.start_offset}&end=${match.end_offset}`} target="_blank" class="block rounded-xl px-3 py-2.5 transition hover:bg-brand-50/60">
          <span class="flex justify-between gap-3 text-sm font-semibold text-slate-800"><span class="truncate">{match.source}</span><span class="shrink-0 text-brand-600">{Math.round(match.score * 100)}%</span></span>
          <span class="mt-1 line-clamp-2 block text-xs leading-5 text-slate-500">{match.snippet}</span>
          <span class="mt-1 block truncate text-[11px] text-slate-400">{match.relative_path} · line {match.line_number}</span>
        </a>
      {/each}
    </div>
  {/if}
</div>

<svelte:window onpointerdown={closeFromOutside} />
