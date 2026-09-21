<script lang="ts">
  import type { ContractConflict } from "../../lib/types";

  interface Props {
    conflict: ContractConflict;
  }

  let { conflict }: Props = $props();
</script>

<article
  id={`conflict-${conflict.id}`}
  class="scroll-mt-28 overflow-hidden rounded-2xl border border-red-200 bg-white shadow-lg shadow-red-100/40 transition target:border-red-500 target:ring-4 target:ring-red-100"
>
  <header class="flex flex-wrap items-start justify-between gap-4 border-b border-red-100 bg-red-50/60 px-6 py-5">
    <div>
      <p class="text-xs font-bold uppercase tracking-[0.14em] text-red-600">Possible contradiction</p>
      <p class="mt-2 text-sm text-slate-600">
        {conflict.scope === "within_contract"
          ? "Found within one contract"
          : `Contracts share ${conflict.shared_parties.join(" · ") || "a common party"}`}
      </p>
    </div>
    <span class="rounded-full border border-red-200 bg-white px-3 py-1.5 text-xs font-bold text-red-700">
      {Math.round(conflict.confidence * 100)}% confidence
    </span>
  </header>

  <div class="grid gap-px bg-red-100 lg:grid-cols-2">
    {#each conflict.clauses as clause, index}
      <section class="bg-white p-6" aria-label={`Conflicting clause ${index + 1}`}>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Clause {index + 1}</span>
          <a
            href={`/contracts/${clause.contract_id}/text`}
            target="_blank"
            class="max-w-xs truncate text-sm font-semibold text-brand-600 hover:underline"
            title={clause.relative_path}
          >
            {clause.source} ↗
          </a>
        </div>
        <div class="mt-4 flex flex-wrap gap-2">
          {#each clause.categories as category}
            <span class="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
              {category.name} · {Math.round(category.confidence * 100)}%
            </span>
          {/each}
        </div>
        <p class="mt-4 whitespace-pre-wrap font-sans text-sm leading-6 text-slate-700">{clause.text}</p>
      </section>
    {/each}
  </div>
</article>
