import { readdir, stat } from "node:fs/promises";

export async function collectFiles(dir: string, ext: string): Promise<string[]> {
  const results: string[] = [];
  const entries = await readdir(dir, { withFileTypes: true }).catch(() => [] as never[]);
  for (const e of entries as { name: string; isDirectory(): boolean }[]) {
    const full = `${dir}/${e.name}`;
    if (e.isDirectory()) {
      const nested = await collectFiles(full, ext);
      results.push(...nested);
    } else if (e.name.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}
