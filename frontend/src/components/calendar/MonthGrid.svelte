<script lang="ts">
  import { localDateKey } from "../../lib/calendar";
  import type { CalendarEvent } from "../../lib/types";

  interface Props {
    cursor: Date;
    events: CalendarEvent[];
    onSelect: (event: CalendarEvent) => void;
  }

  interface CalendarDay {
    date: Date;
    key: string;
    events: CalendarEvent[];
    muted: boolean;
  }

  let { cursor, events, onSelect }: Props = $props();
  const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  let days = $derived.by(() => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const first = new Date(year, month, 1);
    const start = new Date(year, month, 1 - ((first.getDay() + 6) % 7));
    const byDate = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      if (!byDate.has(event.date)) byDate.set(event.date, []);
      byDate.get(event.date)!.push(event);
    }
    return Array.from({ length: 42 }, (_, offset): CalendarDay => {
      const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + offset);
      return { date, key: localDateKey(date), events: byDate.get(localDateKey(date)) || [], muted: date.getMonth() !== month };
    });
  });

  function eventColour(summary: string): string {
    const value = summary.toLowerCase();
    if (/payment|delivery|performance/.test(value)) return "bg-emerald-50 text-emerald-800 border-emerald-200";
    if (/termination|expiration|end date|warranty/.test(value)) return "bg-red-50 text-red-800 border-red-200";
    if (/effective|commencement|start/.test(value)) return "bg-blue-50 text-blue-800 border-blue-200";
    return "bg-amber-50 text-amber-800 border-amber-200";
  }
</script>

<div class="grid grid-cols-7 border-b border-l border-slate-200 bg-white">
  {#each weekdays as weekday}<div class="border-r border-t border-slate-200 px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-400">{weekday}</div>{/each}
  {#each days as day}
    <div class="min-h-32 border-r border-t border-slate-200 p-2 transition hover:bg-brand-50/20 {day.muted ? 'bg-slate-50/70 text-slate-400' : 'bg-white'}">
      <span class="grid h-7 w-7 place-items-center rounded-full text-xs font-semibold {day.key === localDateKey(new Date()) ? 'bg-brand-600 text-white' : ''}">{day.date.getDate()}</span>
      <div class="mt-1 space-y-1">
        {#each day.events.slice(0, 3) as event}
          <button type="button" class="block w-full truncate rounded-md border px-2 py-1 text-left text-[11px] font-semibold transition hover:brightness-95 {eventColour(event.summary)}" onclick={() => onSelect(event)} title={`Open ${event.summary} details`}>
            {event.summary}<span class="block truncate text-[9px] font-normal opacity-70">{event.source}</span>
          </button>
        {/each}
        {#if day.events.length > 3}<p class="px-1 text-[10px] font-semibold text-slate-400">+{day.events.length - 3} more</p>{/if}
      </div>
    </div>
  {/each}
</div>
