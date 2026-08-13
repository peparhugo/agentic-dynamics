import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { BuildContext, Plugin } from '../types';

function titleFromFilename(filename: string): string {
  const stem = path.basename(filename, path.extname(filename));
  return stem.replace(/[-_]+/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function parseDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function parseTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map(tag => tag.trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map(tag => tag.trim()).filter(Boolean);
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async entry => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async beforeBuild(context: BuildContext): Promise<void> {
    let files: string[];
    try {
      files = await markdownFiles(context.contentDir);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        throw new Error(`Content directory does not exist: ${context.contentDir}`);
      }
      throw error;
    }

    context.pages = await Promise.all(files.map(async sourcePath => {
      const relativePath = path.relative(context.contentDir, sourcePath);
      const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
      const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
      const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
        ? parsed.data.title.trim()
        : titleFromFilename(sourcePath);
      return {
        title,
        date: parseDate(parsed.data.date),
        tags: parseTags(parsed.data.tags),
        sourcePath,
        outputPath: path.join(context.outputDir, outputRelativePath),
        url: outputRelativePath.split(path.sep).map(encodeURIComponent).join('/'),
        html: await marked.parse(parsed.content),
        data: parsed.data
      };
    }));

    context.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) {
        return right.date.localeCompare(left.date);
      }
      return left.title.localeCompare(right.title);
    });
  }
}
