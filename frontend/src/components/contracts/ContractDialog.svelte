<script lang="ts">
  import { deleteContract } from "../../lib/api";
  import { groupClauses, lifecycle } from "../../lib/contracts";
  import type { ContractConflict, ContractRecord, GroupedClause } from "../../lib/types";

  interface Props {
    contract: ContractRecord;
    conflicts: ContractConflict[];
    onClose: () => void;
    onDeleted: (source: string) => void | Promise<void>;
    onError: (message: string) => void;
    onConflictSelect: (conflictId: string) => void | Promise<void>;
  }

  let { contract, conflicts, onClose, onDeleted, onError, onConflictSelect }: Props = $props();
  let deleting = $state(false);
  let lifecycleState = $derived(lifecycle(contract));
  let parties = $derived([...new Set(contract.parties.map((party) => party.canonical_name || party.text))]);
  let clauses = $derived(groupClauses(contract.clauses));

  function conflictForClause(clause: GroupedClause): ContractConflict | undefined {
    const ids = new Set(clause.clauseIds);
    return conflicts.find((conflict) => conflict.clauses.some((item) => ids.has(item.id)));
  }

  async function remove(): Promise<void> {
    if (!confirm(`Delete ${contract.source} and all of its extracted data?`)) return;
    deleting = true;
    try {
      await deleteContract(contract.id);
      await onDeleted(contract.source);
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : "Could not delete the contract.");
      deleting = false;
    }
  }
</script>

<div class="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-5 backdrop-blur-sm" role="presentation" onclick={(event) => event.target === event.currentTarget && onClose()}>
  <div class="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-white/80 bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
    <header class="flex items-start justify-between gap-5 border-b border-slate-200 px-7 py-6">
      <div class="min-w-0"><p class="text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Contract details</p><div class="mt-2 flex items-center gap-3"><h2 id="dialog-title" class="truncate text-2xl font-bold tracking-tight text-slate-950">{contract.source}</h2><span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{lifecycleState.label}</span></div><div class="mt-4 flex flex-wrap items-center gap-3"><a href={`/contracts/${contract.id}/text`} target="_blank" class="text-sm font-semibold text-brand-600 hover:underline">Open extracted text ↗</a><button type="button" disabled={deleting} class="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:opacity-50" onclick={remove}>{deleting ? "Deleting…" : "Delete contract"}</button></div></div>
      <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-xl text-slate-500 hover:bg-slate-200" onclick={onClose} aria-label="Close contract details">×</button>
    </header>
    <div class="grid gap-5 border-b border-slate-200 bg-slate-50/70 px-7 py-5 md:grid-cols-2">
      <div><span class="text-xs font-bold uppercase tracking-wider text-slate-400">Parties</span><div class="mt-2 flex flex-wrap gap-2">{#each parties as party}<span class="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm">{party}</span>{/each}{#if !parties.length}<span class="text-sm text-slate-400">No parties identified</span>{/if}</div></div>
      <div><span class="text-xs font-bold uppercase tracking-wider text-slate-400">Contract term</span><p class="mt-2 text-sm font-semibold text-slate-700">{lifecycleState.term}</p></div>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto px-7 py-6">
      <div class="mb-4 flex items-center justify-between"><h3 class="font-bold text-slate-900">Extracted clauses</h3><span class="text-xs font-semibold text-slate-400">{clauses.length} clauses</span></div>
      <div class="space-y-3">
        {#each clauses as clause}
          {@const conflict = conflictForClause(clause)}
          <button
            type="button"
            disabled={!conflict}
            class="block w-full rounded-xl border p-4 text-left transition {conflict ? 'border-red-300 bg-red-50/70 hover:border-red-500 hover:shadow-md hover:shadow-red-100' : 'border-slate-200 hover:border-sky-100 hover:shadow-sm'}"
            onclick={() => conflict && onConflictSelect(conflict.id)}
          >
            <span class="flex flex-wrap items-center gap-2">
              {#each clause.categories as category}<span class="rounded-full px-2.5 py-1 text-xs font-semibold {conflict ? 'bg-red-100 text-red-700' : 'bg-brand-50 text-brand-600'}">{category.name} · {Math.round(category.confidence * 100)}%</span>{/each}
              {#if conflict}<span class="ml-auto text-xs font-bold text-red-700">Possible conflict · View →</span>{/if}
            </span>
            <span class="mt-3 block whitespace-pre-wrap font-sans text-sm leading-6 text-slate-600">{clause.text}</span>
          </button>
        {/each}
        {#if !clauses.length}<p class="rounded-xl bg-slate-50 p-5 text-sm text-slate-400">No clauses identified.</p>{/if}
      </div>
    </div>
  </div>
</div>

<svelte:window onkeydown={(event) => event.key === "Escape" && onClose()} />
