<script lang="ts">
  import { extractionConfidence, groupClauses } from "../../lib/contracts";
  import type { ContractRecord, MetricIconName } from "../../lib/types";
  import MetricIcon from "./MetricIcon.svelte";

  interface Props {
    contracts: ContractRecord[];
  }

  interface Metric {
    icon: MetricIconName;
    label: string;
    value: number | string;
    tone: string;
  }

  let { contracts }: Props = $props();
  let complete = $derived(contracts.filter((contract) => contract.status === "complete"));
  let confidences = $derived(complete.map(extractionConfidence).filter((value) => value !== null));
  let metrics = $derived<Metric[]>([
    { icon: "contracts", label: "Contracts", value: contracts.length, tone: "bg-blue-50 text-blue-600" },
    { icon: "clauses", label: "Clauses Found", value: complete.reduce((sum, contract) => sum + groupClauses(contract.clauses).length, 0), tone: "bg-violet-50 text-violet-600" },
    { icon: "dates", label: "Dates", value: complete.reduce((sum, contract) => sum + contract.dates.length, 0), tone: "bg-teal-50 text-teal-600" },
    { icon: "confidence", label: "Average Confidence", value: confidences.length ? `${Math.round(confidences.reduce((sum, value) => sum + value, 0) / confidences.length * 100)}%` : "—", tone: "bg-amber-50 text-amber-600" },
  ]);
</script>

<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
  {#each metrics as metric}
    <article class="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-300 hover:-translate-y-0.5 hover:border-sky-100 hover:shadow-lg hover:shadow-sky-100/60">
      <MetricIcon name={metric.icon} tone={metric.tone} />
      <div><strong class="block text-2xl font-bold tracking-tight text-slate-950">{metric.value}</strong><span class="text-sm text-slate-500">{metric.label}</span></div>
    </article>
  {/each}
</div>
