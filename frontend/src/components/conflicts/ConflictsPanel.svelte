<script lang="ts">
  import type { ContractConflict } from "../../lib/types";
  import ConflictCard from "./ConflictCard.svelte";

  interface Props {
    conflicts: ContractConflict[];
  }

  let { conflicts }: Props = $props();
</script>

<section class="mx-auto max-w-7xl px-5 py-14 md:px-8 md:py-20" aria-labelledby="conflicts-title">
  <div>
    <p class="inline-flex rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-red-600">Portfolio review</p>
    <h1 id="conflicts-title" class="mt-4 text-4xl font-bold tracking-[-0.03em] text-slate-950 md:text-5xl">Possible conflicts</h1>
    <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
      Model-identified contradictions within a contract or between contracts involving a common party. Every result should be reviewed against its full agreement context.
    </p>
  </div>

  {#if conflicts.length}
    <div class="mt-10 space-y-6">
      {#each conflicts as conflict (conflict.id)}
        <ConflictCard {conflict} />
      {/each}
    </div>
  {:else}
    <div class="mt-10 grid min-h-64 place-items-center rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-xl shadow-sky-100/40">
      <div>
        <span class="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-emerald-50 text-emerald-600" aria-hidden="true">✓</span>
        <h2 class="mt-4 text-lg font-bold text-slate-900">No possible conflicts found</h2>
        <p class="mt-2 text-sm text-slate-500">Newly uploaded contracts are checked automatically.</p>
      </div>
    </div>
  {/if}
</section>
