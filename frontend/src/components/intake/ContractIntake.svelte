<script lang="ts">
  import { uploadContracts } from "../../lib/api";
  import { collectDropEntries, supportedEntries } from "../../lib/files";
  import type { UploadEntry } from "../../lib/types";

  interface Props {
    onComplete: () => void | Promise<void>;
    onToast: (message: string, error?: boolean) => void;
  }

  let { onComplete, onToast }: Props = $props();
  let folderInput: HTMLInputElement;
  let fileInput: HTMLInputElement;
  let dragging = $state(false);
  let processing = $state(false);
  let entries = $state<UploadEntry[]>([]);
  let message = $state("Preparing files…");

  async function acceptSelection(selection: UploadEntry[]): Promise<void> {
    if (processing) return;
    const accepted = supportedEntries(selection);
    const skipped = selection.length - accepted.length;
    if (!accepted.length) return onToast("No supported contracts were found in that selection.", true);
    entries = accepted;
    processing = true;
    message = "Reading contracts and loading local extraction models…";
    try {
      const result = await uploadContracts(accepted);
      const failures = result.contracts.filter((contract) => contract.status === "failed").length;
      message = `${result.contracts.length} contract${result.contracts.length === 1 ? "" : "s"} stored in PostgreSQL.`;
      onToast(failures ? `Processing completed with ${failures} failed file${failures === 1 ? "" : "s"}.` : "Contract intelligence is ready.", failures > 0);
      if (result.conflict_analysis_error) {
        onToast(`Contracts were stored, but conflict analysis failed: ${result.conflict_analysis_error}`, true);
      }
      await onComplete();
    } catch (error: unknown) {
      message = "Processing stopped. Check the local server and database.";
      onToast(error instanceof Error ? error.message : "Contract processing failed.", true);
    } finally {
      processing = false;
      if (skipped) onToast(`${skipped} unsupported file${skipped === 1 ? " was" : "s were"} skipped.`, false);
    }
  }

  function reset(): void {
    entries = [];
    message = "Preparing files…";
    if (folderInput) folderInput.value = "";
    if (fileInput) fileInput.value = "";
  }

  function entriesFromInput(event: Event, preserveFolderPath: boolean): UploadEntry[] {
    const input = event.currentTarget as HTMLInputElement;
    return [...(input.files || [])].map((file) => ({
      file,
      path: preserveFolderPath ? file.webkitRelativePath || file.name : file.name,
    }));
  }

  async function drop(event: DragEvent): Promise<void> {
    event.preventDefault();
    dragging = false;
    if (event.dataTransfer) acceptSelection(await collectDropEntries(event.dataTransfer));
  }
</script>

<section class="bg-[radial-gradient(80%_40%_at_50%_0%,rgba(51,144,219,0.20),transparent_78%)] px-5 pb-20 pt-16 md:px-8 md:pt-24" aria-labelledby="intake-title">
  <div class="mx-auto max-w-4xl text-center">
    <p class="inline-flex rounded-full border border-brand-500/30 bg-brand-50/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600 shadow-sm">Contract intelligence</p>
    <h1 id="intake-title" class="mt-6 text-4xl font-bold tracking-[-0.035em] text-slate-950 sm:text-5xl lg:text-6xl">
      Contracts, clearly understood.
    </h1>
    <p class="mx-auto mt-6 max-w-2xl text-base leading-7 text-slate-500 md:text-lg">Upload one contract, several files, or a complete folder. Clauses, parties, and dates become a clear, searchable workspace.</p>
  </div>

  <div class="mx-auto mt-12 max-w-6xl">
    <input bind:this={folderInput} onchange={(event) => acceptSelection(entriesFromInput(event, true))} type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.txt" webkitdirectory multiple hidden />
    <input bind:this={fileInput} onchange={(event) => acceptSelection(entriesFromInput(event, false))} type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.txt" multiple hidden />

    {#if !entries.length}
      <div
        role="region"
        aria-label="Contract file dropzone"
        class="flex min-h-[22rem] flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center shadow-xl shadow-sky-100/50 transition duration-300 sm:p-12 {dragging ? 'scale-[1.01] border-brand-500 bg-brand-50' : 'border-slate-300 bg-[radial-gradient(70%_55%_at_0%_0%,rgba(51,144,219,0.12),transparent),radial-gradient(70%_55%_at_100%_100%,rgba(99,102,241,0.10),transparent),white] hover:border-brand-500/60 hover:shadow-2xl hover:shadow-brand-100'}"
        ondragenter={(event) => { event.preventDefault(); dragging = true; }}
        ondragover={(event) => event.preventDefault()}
        ondragleave={() => dragging = false}
        ondrop={drop}
      >
        <span class="grid h-16 w-16 place-items-center rounded-2xl border border-brand-100 bg-white text-brand-600 shadow-sm">
          <svg class="block h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7.5V18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-7l-2-3H5a2 2 0 0 0-2 2v1.5Z"/><path d="M12 11v6m-3-3 3-3 3 3"/></svg>
        </span>
        <h2 class="mt-6 text-2xl font-bold tracking-tight text-slate-950">Drop contracts here</h2>
        <p class="mt-2 text-sm text-slate-500">Files and folders are both welcome</p>
        <div class="mt-6 flex flex-wrap justify-center gap-3">
          <button type="button" class="h-12 rounded-xl bg-brand-500 px-6 text-sm font-semibold text-white shadow-md shadow-brand-100 transition hover:-translate-y-0.5 hover:bg-brand-600 hover:shadow-lg" onclick={() => folderInput.click()}>Choose folder</button>
          <button type="button" class="h-12 rounded-xl border border-slate-200 bg-white px-6 text-sm font-semibold text-slate-800 shadow-sm transition hover:-translate-y-0.5 hover:bg-slate-50" onclick={() => fileInput.click()}>Choose files</button>
        </div>
        <span class="mt-7 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">PDF · PNG · JPEG · DOCX · TXT</span>
      </div>
    {:else}
      <div class="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl shadow-sky-100/50">
        <div class="flex items-start justify-between gap-5">
          <div><h2 class="text-lg font-bold text-slate-900">{entries[0].path.includes("/") ? entries[0].path.split("/")[0] : "Selected files"}</h2><p class="mt-1 text-sm text-slate-500">{entries.length} supported file{entries.length === 1 ? "" : "s"}</p></div>
          <button type="button" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-brand-600 shadow-sm transition hover:bg-slate-50 disabled:opacity-50" disabled={processing} onclick={reset}>New selection</button>
        </div>
        <div class="mt-7 h-2 overflow-hidden rounded-full bg-slate-100"><span class="block h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500 transition-all {processing ? 'w-3/4 animate-pulse' : 'w-full'}"></span></div>
        <p class="mt-4 text-sm text-slate-500">{message}</p>
        <div class="mt-6 flex flex-wrap gap-2">{#each entries.slice(0, 18) as entry}<span class="max-w-64 truncate rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600" title={entry.path}>{entry.path}</span>{/each}</div>
      </div>
    {/if}
  </div>
</section>
