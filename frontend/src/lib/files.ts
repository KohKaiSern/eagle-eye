import type { UploadEntry } from "./types";

const SUPPORTED = new Set(["pdf", "png", "jpg", "jpeg", "docx", "txt"]);

export function supportedEntries(entries: UploadEntry[]): UploadEntry[] {
  return entries.filter(({ file }) => {
    const extension = file.name.split(".").pop()?.toLowerCase();
    return extension ? SUPPORTED.has(extension) : false;
  });
}

export async function collectDropEntries(dataTransfer: DataTransfer): Promise<UploadEntry[]> {
  const roots = [...dataTransfer.items]
    .map((item) => item.webkitGetAsEntry())
    .filter((entry): entry is FileSystemEntry => Boolean(entry));
  if (!roots.length) return [...dataTransfer.files].map((file) => ({ file, path: file.name }));
  const files: UploadEntry[] = [];
  for (const entry of roots) await walkEntry(entry, "", files);
  return files;
}

async function walkEntry(entry: FileSystemEntry, parentPath: string, output: UploadEntry[]): Promise<void> {
  const path = parentPath ? `${parentPath}/${entry.name}` : entry.name;
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
    output.push({ file, path });
  } else if (entry.isDirectory) {
    const reader = (entry as FileSystemDirectoryEntry).createReader();
    while (true) {
      const children = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
      if (!children.length) break;
      for (const child of children) await walkEntry(child, path, output);
    }
  }
}
