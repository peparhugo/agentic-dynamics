import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

export interface CacheManifest {
  version: 1;
  pages: Record<string, { sourceHash: string; templateHash: string }>;
}

export function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

export async function hashDirectory(directory: string): Promise<string> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(async (entry) => {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) return hashDirectory(file).then((value) => `${entry.name}/${value}`);
      if (entry.isFile()) return readFile(file, 'utf8').then((value) => `${entry.name}:${hash(value)}`);
      return '';
    }));
    return hash(files.sort().join('\n'));
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return hash('');
    throw error;
  }
}
