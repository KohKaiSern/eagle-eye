<script lang="ts">
  import type { MetricIconName } from "../../lib/types";

  interface Props {
    name: MetricIconName;
    tone: string;
  }

  let { name, tone }: Props = $props();
</script>

<span class="grid h-12 w-12 shrink-0 place-items-center rounded-xl {tone}" aria-hidden="true">
  {#if name === "contracts"}
    <svg class="block h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></svg>
  {:else if name === "clauses"}
    <svg class="block h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="m8 12 2.5 2.5L16 9"/></svg>
  {:else if name === "dates"}
    <svg class="block h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>
  {:else}
    <svg class="block h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13a8 8 0 1 1-15.5-4M12 12l4-4"/><path d="M12 2v2M22 12h-2M4.9 4.9l1.4 1.4M19.1 4.9l-1.4 1.4"/></svg>
  {/if}
</span>
