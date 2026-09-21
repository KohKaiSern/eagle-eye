<script lang="ts">
  import { extractionConfidence, groupClauses, lifecycle } from "../../lib/contracts";
  import type { ContractRecord, LifecycleStatus } from "../../lib/types";

  interface Props {
    contracts: ContractRecord[];
    onSelect: (contract: ContractRecord) => void;
  }

  let { contracts, onSelect }: Props = $props();
  const statusStyles: Record<LifecycleStatus, string> = {
    active: "bg-emerald-50 text-emerald-700",
    upcoming: "bg-blue-50 text-blue-700",
    expired: "bg-slate-100 text-slate-600",
    undated: "bg-amber-50 text-amber-700",
    review: "bg-red-50 text-red-700",
    failed: "bg-red-50 text-red-700",
  };
</script>

<div class="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xl shadow-sky-100/40">
  {#if !contracts.length}
    <div class="grid min-h-60 place-items-center p-10 text-center"><div><strong class="text-lg text-slate-900">No contracts yet</strong><p class="mt-2 text-sm text-slate-500">Processed contracts will appear here.</p></div></div>
  {:else}
    <table class="w-full min-w-[900px] border-collapse text-left">
      <thead><tr class="border-b border-slate-200 bg-slate-50/70 text-xs uppercase tracking-wider text-slate-400"><th class="px-5 py-3.5">Contract</th><th class="px-4 py-3.5">Parties</th><th class="px-4 py-3.5 text-center">Clauses</th><th class="px-4 py-3.5 text-center">Dates</th><th class="px-4 py-3.5 text-center">Confidence</th><th class="px-5 py-3.5">Status</th></tr></thead>
      <tbody>
        {#each contracts as contract}
          {@const state = lifecycle(contract)}
          {@const confidence = extractionConfidence(contract)}
          <tr class="cursor-pointer border-b border-l-4 border-slate-100 transition last:border-b-0 hover:bg-brand-50/35 {contract.has_conflicts ? 'border-l-red-500 bg-red-50/45' : state.status === 'active' ? 'border-l-transparent bg-emerald-50/30' : 'border-l-transparent'}" onclick={() => onSelect(contract)}>
            <td class="px-5 py-4"><div class="flex items-center gap-3"><span class="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-[10px] font-black uppercase text-brand-600">{contract.file_type}</span><div class="min-w-0"><a href={`/contracts/${contract.id}/text`} target="_blank" onclick={(event) => event.stopPropagation()} class="block max-w-xs truncate font-semibold text-slate-900 hover:text-brand-600">{contract.source}</a><span class="block max-w-xs truncate text-xs text-slate-400">{contract.relative_path}</span></div></div></td>
            <td class="max-w-xs truncate px-4 py-4 text-sm">{contract.parties.length ? contract.parties.map((party) => party.canonical_name || party.text).join(" · ") : "Not identified"}</td>
            <td class="px-4 py-4 text-center text-sm font-semibold">{groupClauses(contract.clauses).length}</td>
            <td class="px-4 py-4 text-center text-sm font-semibold">{contract.dates.length}</td>
            <td class="px-4 py-4 text-center text-sm font-semibold">{confidence === null ? "—" : `${Math.round(confidence * 100)}%`}</td>
            <td class="px-5 py-4"><div class="flex flex-wrap gap-2"><span class="rounded-full px-3 py-1.5 text-xs font-bold {statusStyles[state.status]}">{state.label}</span>{#if contract.has_conflicts}<span class="rounded-full bg-red-100 px-3 py-1.5 text-xs font-bold text-red-700">Possible conflict</span>{/if}</div></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
