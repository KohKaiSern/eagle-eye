<script lang="ts">
  import type { WorkspaceTab } from "../../lib/types";

  interface Props {
    active: WorkspaceTab;
    onChange: (tab: WorkspaceTab) => void;
  }

  interface TabDefinition {
    id: WorkspaceTab;
    label: string;
  }

  let { active, onChange }: Props = $props();
  const tabs: TabDefinition[] = [
    { id: "intake", label: "Contract intake" },
    { id: "calendar", label: "Calendar" },
    { id: "contracts", label: "Contracts" },
    { id: "conflicts", label: "Conflicts" },
  ];

  function handleKey(event: KeyboardEvent, index: number): void {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let next = index;
    if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    onChange(tabs[next].id);
    const button = (event.currentTarget as HTMLElement).parentElement?.children[next] as HTMLElement | undefined;
    button?.focus();
  }
</script>

<div class="flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50/80 p-1" role="tablist" aria-label="Contract workspace">
  {#each tabs as tab, index}
    <button
      type="button"
      role="tab"
      aria-selected={active === tab.id}
      tabindex={active === tab.id ? 0 : -1}
      class="rounded-lg px-3 py-2 text-sm font-medium transition-all sm:px-4 {active === tab.id ? 'bg-white text-brand-600 shadow-sm ring-1 ring-slate-200/80' : 'text-slate-500 hover:bg-white/70 hover:text-slate-900'}"
      onclick={() => onChange(tab.id)}
      onkeydown={(event) => handleKey(event, index)}
    >
      {tab.label}
    </button>
  {/each}
</div>
