<script lang="ts">
  import type { ToastState } from "../../lib/types";

  interface Props {
    toast: ToastState | null;
  }

  let { toast }: Props = $props();
</script>

{#if toast}
  <div class="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-white shadow-2xl {toast.error ? 'bg-red-600' : 'bg-slate-950'}" role="status">
    {toast.message}
  </div>
{/if}
