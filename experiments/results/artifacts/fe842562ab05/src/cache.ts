import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

export async function hashFile(filePath: string): Promise<string> {
  return createHash('sha256').update(await readFile(filePath)).digest('hex');
}

export function hashText(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}
