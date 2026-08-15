import { promises as fs } from 'fs';
import path from 'path';

export interface MarkdownFile {
  name: string;
  path: string;
  content: string;
}

export async function readMarkdownFiles(contentDir: string): Promise<MarkdownFile[]> {
  const files: MarkdownFile[] = [];

  try {
    const entries = await fs.readdir(contentDir);
    for (const entry of entries) {
      if (entry.endsWith('.md')) {
        const filePath = path.join(contentDir, entry);
        const content = await fs.readFile(filePath, 'utf-8');
        files.push({
          name: entry,
          path: filePath,
          content
        });
      }
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      await fs.mkdir(contentDir, { recursive: true });
    } else {
      throw error;
    }
  }

  return files;
}

export async function writeFile(filePath: string, content: string): Promise<void> {
  const dir = path.dirname(filePath);
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

export async function ensureDir(dirPath: string): Promise<void> {
  await fs.mkdir(dirPath, { recursive: true });
}
