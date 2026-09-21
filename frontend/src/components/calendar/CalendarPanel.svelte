<script lang="ts">
  import type { CalendarEvent } from "../../lib/types";
  import CalendarEventDialog from "./CalendarEventDialog.svelte";
  import MonthGrid from "./MonthGrid.svelte";

  interface Props {
    events: CalendarEvent[];
  }

  let { events }: Props = $props();
  let cursor = $state(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  let selectedEvent = $state<CalendarEvent | null>(null);
  let monthName = $derived(new Intl.DateTimeFormat("en-SG", { month: "long", year: "numeric" }).format(cursor));
  let monthPrefix = $derived(`${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-`);
  let monthCount = $derived(events.filter((event) => event.date.startsWith(monthPrefix)).length);

  function moveMonth(amount: number): void {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + amount, 1);
  }
</script>

<section class="mx-auto max-w-7xl px-5 py-14 md:px-8 md:py-20" aria-labelledby="calendar-title">
  <div class="flex flex-wrap items-end justify-between gap-6">
    <div><p class="inline-flex rounded-full border border-brand-500/30 bg-brand-50/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Dates and deadlines</p><h1 id="calendar-title" class="mt-4 text-4xl font-bold tracking-[-0.03em] text-slate-950 md:text-5xl">Contract calendar</h1><p class="mt-3 text-sm text-slate-500">{monthCount} event{monthCount === 1 ? "" : "s"} this month · {events.length} total</p></div>
    <div class="flex items-center gap-2">
      <a href="/api/calendar.ics?download=true" class="mr-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-100 transition hover:-translate-y-0.5 hover:bg-brand-600">Export .ics</a>
      <button type="button" class="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-lg shadow-sm transition hover:bg-slate-50" onclick={() => moveMonth(-1)} aria-label="Previous month">‹</button>
      <button type="button" class="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold shadow-sm transition hover:bg-slate-50" onclick={() => cursor = new Date(new Date().getFullYear(), new Date().getMonth(), 1)}>Today</button>
      <button type="button" class="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-lg shadow-sm transition hover:bg-slate-50" onclick={() => moveMonth(1)} aria-label="Next month">›</button>
    </div>
  </div>
  <div class="mt-10 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-sky-100/50">
    <div class="bg-white px-5 py-4 text-center text-lg font-bold text-slate-900">{monthName}</div>
    <div class="overflow-x-auto"><div class="min-w-[900px]"><MonthGrid {cursor} {events} onSelect={(event) => selectedEvent = event} /></div></div>
  </div>
</section>

{#if selectedEvent}<CalendarEventDialog event={selectedEvent} onClose={() => selectedEvent = null} />{/if}
