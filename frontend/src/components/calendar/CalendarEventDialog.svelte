<script lang="ts">
  import type { CalendarEvent } from "../../lib/types";

  interface Props {
    event: CalendarEvent;
    onClose: () => void;
  }

  let { event, onClose }: Props = $props();

  function displayDate(value: string): string {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }

  function sourceTextUrl(): string {
    const base = `/contracts/${event.contractId}/text`;
    return Number.isInteger(event.startOffset) && Number.isInteger(event.endOffset)
      ? `${base}?start=${event.startOffset}&end=${event.endOffset}`
      : base;
  }
</script>

<div class="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-5 backdrop-blur-sm" role="presentation" onclick={(click) => click.target === click.currentTarget && onClose()}>
  <div class="w-full max-w-xl overflow-hidden rounded-2xl border border-white/80 bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="calendar-event-title">
    <header class="flex items-start justify-between gap-5 border-b border-slate-200 px-6 py-5">
      <div><p class="text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Contract date</p><h2 id="calendar-event-title" class="mt-2 text-2xl font-bold tracking-tight text-slate-950">{event.summary}</h2></div>
      <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-xl text-slate-500 transition hover:bg-slate-200" onclick={onClose} aria-label="Close date details">×</button>
    </header>
    <div class="space-y-5 px-6 py-6">
      <dl class="grid gap-4 sm:grid-cols-2">
        <div><dt class="text-xs font-semibold uppercase tracking-wider text-slate-400">Date</dt><dd class="mt-1 text-sm font-semibold text-slate-800">{displayDate(event.date)}</dd></div>
        <div><dt class="text-xs font-semibold uppercase tracking-wider text-slate-400">Contract</dt><dd class="mt-1 text-sm font-semibold text-slate-800">{event.source}</dd></div>
        <div><dt class="text-xs font-semibold uppercase tracking-wider text-slate-400">Confidence</dt><dd class="mt-1 text-sm font-semibold text-slate-800">{Math.round(event.confidence * 100)}%</dd></div>
        <div><dt class="text-xs font-semibold uppercase tracking-wider text-slate-400">Provenance</dt><dd class="mt-1 text-sm font-semibold capitalize text-slate-800">{event.provenance}</dd></div>
        {#if Number.isInteger(event.startOffset) && Number.isInteger(event.endOffset)}<div><dt class="text-xs font-semibold uppercase tracking-wider text-slate-400">Source location</dt><dd class="mt-1 text-sm font-semibold text-slate-800">Characters {event.startOffset}–{event.endOffset}</dd></div>{/if}
      </dl>
      <div><h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Source evidence</h3><p class="mt-2 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">{event.evidence || "No source evidence stored."}</p></div>
      {#if event.contractId}<a class="inline-flex rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-600" href={sourceTextUrl()} target="_blank">Open source text ↗</a>{/if}
    </div>
  </div>
</div>

<svelte:window onkeydown={(keydown) => keydown.key === "Escape" && onClose()} />
