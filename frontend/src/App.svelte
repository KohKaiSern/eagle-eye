<script lang="ts">
  import { onMount, tick } from "svelte";
  import CalendarPanel from "./components/calendar/CalendarPanel.svelte";
  import ContractsPanel from "./components/contracts/ContractsPanel.svelte";
  import ConflictsPanel from "./components/conflicts/ConflictsPanel.svelte";
  import ContractIntake from "./components/intake/ContractIntake.svelte";
  import AppHeader from "./components/layout/AppHeader.svelte";
  import Toast from "./components/shared/Toast.svelte";
  import ContractTextPage from "./components/text/ContractTextPage.svelte";
  import { fetchCalendar, fetchConflicts, fetchContracts } from "./lib/api";
  import { parseCalendar } from "./lib/calendar";
  import type { CalendarEvent, ContractConflict, ContractRecord, ToastState, WorkspaceTab } from "./lib/types";

  const textRoute = /^\/contracts\/([^/]+)\/text\/?$/.exec(location.pathname);
  let activeTab = $state(tabFromHash());
  let contracts = $state<ContractRecord[]>([]);
  let conflicts = $state<ContractConflict[]>([]);
  let calendarEvents = $state<CalendarEvent[]>([]);
  let toast = $state<ToastState | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  onMount(() => {
    if (!textRoute) loadWorkspace().then(scrollToHashConflict);
    const syncHash = (): void => {
      activeTab = tabFromHash();
      scrollToHashConflict();
    };
    addEventListener("hashchange", syncHash);
    return () => removeEventListener("hashchange", syncHash);
  });

  function tabFromHash(): WorkspaceTab {
    const value = location.hash.slice(1);
    if (value.startsWith("conflict-")) return "conflicts";
    return value === "calendar" || value === "contracts" || value === "conflicts" ? value : "intake";
  }

  function changeTab(tab: WorkspaceTab): void {
    activeTab = tab;
    history.pushState(null, "", `#${tab}`);
    scrollTo({ top: 0, behavior: "auto" });
  }

  async function loadWorkspace(): Promise<void> {
    try {
      const [contractResult, conflictResult, calendar] = await Promise.all([
        fetchContracts(),
        fetchConflicts(),
        fetchCalendar(),
      ]);
      contracts = contractResult.contracts;
      conflicts = conflictResult.conflicts;
      calendarEvents = parseCalendar(calendar);
    } catch (error: unknown) {
      showToast(error instanceof Error ? error.message : "Could not load the workspace.", true);
    }
  }

  async function openConflict(conflictId: string): Promise<void> {
    activeTab = "conflicts";
    history.pushState(null, "", `#conflict-${conflictId}`);
    await scrollToHashConflict();
  }

  async function scrollToHashConflict(): Promise<void> {
    if (!location.hash.startsWith("#conflict-")) return;
    await tick();
    document.querySelector<HTMLElement>(location.hash)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  function showToast(message: string, error = false): void {
    toast = { message, error };
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast = null, 4200);
  }
</script>

{#if textRoute}
  <ContractTextPage contractId={textRoute[1]} />
{:else}
  <AppHeader {activeTab} onTabChange={changeTab} onError={(message) => showToast(message, true)} />
  <main class="min-h-[calc(100vh-4rem)]">
    <div hidden={activeTab !== "intake"}><ContractIntake onComplete={loadWorkspace} onToast={showToast} /></div>
    <div hidden={activeTab !== "calendar"}><CalendarPanel events={calendarEvents} /></div>
    <div hidden={activeTab !== "contracts"}><ContractsPanel {contracts} {conflicts} onRefresh={loadWorkspace} onToast={showToast} onConflictSelect={openConflict} /></div>
    <div hidden={activeTab !== "conflicts"}><ConflictsPanel {conflicts} /></div>
  </main>
  <Toast {toast} />
{/if}
