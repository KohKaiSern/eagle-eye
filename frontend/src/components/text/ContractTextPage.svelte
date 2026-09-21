<script lang="ts">
  import { onMount } from "svelte";
  import { fetchContract } from "../../lib/api";
  import type { ContractRecord } from "../../lib/types";

  interface Props {
    contractId: string;
  }

  let { contractId }: Props = $props();
  let contract = $state<ContractRecord | null>(null);
  let error = $state("");
  let before = $state("");
  let highlight = $state("");
  let after = $state("");

  onMount(async () => {
    try {
      contract = await fetchContract(contractId);
      document.title = `${textFilename(contract.source)} — Eagle Eye`;
      splitText(contract.text?.content || "No text was extracted.");
    } catch (caught: unknown) {
      error = caught instanceof Error ? caught.message : "Could not load the extracted text.";
    }
  });

  function textFilename(source: string): string {
    const dot = source.lastIndexOf(".");
    return `${dot > 0 ? source.slice(0, dot) : source}.txt`;
  }

  function splitText(content: string): void {
    const params = new URLSearchParams(location.search);
    const start = Number.parseInt(params.get("start") || "", 10);
    const end = Number.parseInt(params.get("end") || "", 10);
    if (Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= content.length) {
      before = content.slice(0, start);
      highlight = content.slice(start, end);
      after = content.slice(end);
    } else {
      before = content;
    }
  }
</script>

<main class="min-h-screen bg-[radial-gradient(80%_30%_at_50%_0%,rgba(51,144,219,0.16),transparent_75%)] px-5 py-10 md:py-16">
  <article class="mx-auto max-w-5xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-sky-100/50">
    <header class="border-b border-slate-200 px-8 py-6"><a href="/#contracts" class="text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">← Contracts</a>{#if contract}<h1 class="mt-3 text-2xl font-bold tracking-tight text-slate-950">{textFilename(contract.source)}</h1><p class="mt-1 text-sm text-slate-400">Extracted from {contract.source} · {contract.relative_path}</p>{/if}</header>
    <div class="p-8 md:p-12">{#if error}<p class="rounded-xl bg-red-50 p-5 text-red-700">{error}</p>{:else if !contract}<p class="text-slate-400">Loading extracted text…</p>{:else}<pre class="whitespace-pre-wrap break-words font-sans text-[15px] leading-7 text-slate-700">{before}{#if highlight}<mark class="rounded bg-amber-200 px-0.5">{highlight}</mark>{/if}{after}</pre>{/if}</div>
  </article>
</main>
