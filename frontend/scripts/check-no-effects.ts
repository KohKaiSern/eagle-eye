import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const sourceDirectory = fileURLToPath(new URL("../src/", import.meta.url));
const effectPattern = /\$effect(?:\.pre)?\s*\(/;
const violations: string[] = [];

async function inspect(directory: string): Promise<void> {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await inspect(path);
    } else if ([".ts", ".svelte"].includes(extname(entry.name))) {
      const source = await readFile(path, "utf8");
      if (effectPattern.test(source)) violations.push(relative(sourceDirectory, path));
    }
  }
}

await inspect(sourceDirectory);

if (violations.length) {
  console.error(`Svelte effects are not allowed:\n${violations.join("\n")}`);
  process.exit(1);
}
