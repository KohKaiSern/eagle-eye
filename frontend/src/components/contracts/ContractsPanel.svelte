<script lang="ts">
  import type { ContractConflict, ContractRecord } from "../../lib/types";
  import ContractDialog from "./ContractDialog.svelte";
  import ContractMetrics from "./ContractMetrics.svelte";
  import ContractTable from "./ContractTable.svelte";

  interface Props {
    contracts: ContractRecord[];
    conflicts: ContractConflict[];
    onRefresh: () => void | Promise<void>;
    onToast: (message: string, error?: boolean) => void;
    onConflictSelect: (conflictId: string) => void | Promise<void>;
  }

  let { contracts, conflicts, onRefresh, onToast, onConflictSelect }: Props = $props();
  let selected = $state<ContractRecord | null>(null);

  async function deleted(source: string): Promise<void> {
    selected = null;
    await onRefresh();
    onToast(`${source} was deleted.`, false);
  }

  async function selectConflict(conflictId: string): Promise<void> {
    selected = null;
    await onConflictSelect(conflictId);
  }
</script>

<section class="mx-auto max-w-7xl px-5 py-14 md:px-8 md:py-20" aria-labelledby="contracts-title">
  <div class="flex items-end justify-between gap-5"><div><p class="inline-flex rounded-full border border-brand-500/30 bg-brand-50/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Contract library</p><h1 id="contracts-title" class="mt-4 text-4xl font-bold tracking-[-0.03em] text-slate-950 md:text-5xl">Your contracts</h1><p class="mt-3 max-w-xl text-sm leading-6 text-slate-500">A single view of the parties, clauses, dates, and obligations across your agreements.</p></div><button type="button" class="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50" onclick={onRefresh}>Refresh</button></div>
  <div class="mt-10"><ContractMetrics {contracts} /></div>
  <div class="mt-6"><ContractTable {contracts} onSelect={(contract) => selected = contract} /></div>
</section>

{#if selected}<ContractDialog contract={selected} {conflicts} onClose={() => selected = null} onDeleted={deleted} onError={(message) => onToast(message, true)} onConflictSelect={selectConflict} />{/if}
