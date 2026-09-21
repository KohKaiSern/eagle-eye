<script lang="ts">
  import type { WorkspaceTab } from "../../lib/types";
  import ContractSearch from "../search/ContractSearch.svelte";
  import WorkspaceTabs from "./WorkspaceTabs.svelte";

  interface Props {
    activeTab: WorkspaceTab;
    onTabChange: (tab: WorkspaceTab) => void;
    onError: (message: string) => void;
  }

  let { activeTab, onTabChange, onError }: Props = $props();
</script>

<header class="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
  <div class="mx-auto flex min-h-16 max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-3 md:flex-nowrap md:px-8">
    <WorkspaceTabs active={activeTab} onChange={onTabChange} />
    <div class="order-3 flex w-full justify-end md:order-none md:ml-auto md:flex-1"><ContractSearch {onError} /></div>
  </div>
</header>
