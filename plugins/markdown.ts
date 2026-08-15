import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { CacheManifest, Frontmatter, ParsedMarkdown, Page } from '../index';
import { createHash } from 'node:crypto';
import type { BuildContext, Plugin } from './types';

const markdownExtensions = new Set(['.md', '.markdown']);

function parseSimpleYaml(input: string): Frontmatter {
  const data: Frontmatter = {};
  for (const line of input.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (!key) continue;
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    if (value.startsWith('[') && value.endsWith(']')) data[key] = value.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
    else data[key] = value;
  }
  return data;
}

export function parseMarkdown(source: string): ParsedMarkdown {
  let yaml: Frontmatter = {};
  let markdown = source;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (match) {
    yaml = parseSimpleYaml(match[1]);
    markdown = source.slice(match[0].length);
  }
  const parsed = matter(markdown);
  return { data: { ...parsed.data, ...yaml } as Frontmatter, content: parsed.content };
}

async function markdownFiles(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const child = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, child));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(child);
  }
  return files.sort();
}

function titleFor(filePath: string, data: Frontmatter): string {
  if (typeof data.title === 'string' && data.title.trim()) return data.title.trim();
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function tagsFor(data: Frontmatter): string[] {
  if (Array.isArray(data.tags)) return data.tags.map(String);
  if (typeof data.tags === 'string') return data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export class MarkdownPlugin implements Plugin {
  async onStart(context: BuildContext): Promise<void> {
    context.files = await markdownFiles(context.contentDir);
    for (const relativeSource of context.files) {
      const source = await fs.readFile(path.join(context.contentDir, relativeSource), 'utf8');
      const sourceHash = createHash('sha256').update(source).digest('hex');
      const hashes = (context.metadata.sourceHashes ??= {}) as Record<string, string>;
      hashes[relativeSource.split(path.sep).join('/')] = sourceHash;
      const cached = (context.metadata.cache as CacheManifest | undefined)?.pages[relativeSource.split(path.sep).join('/')];
      const parsed = cached?.sourceHash === sourceHash && cached.frontmatter && cached.markdownContent !== undefined
        ? { data: cached.frontmatter, content: cached.markdownContent }
        : parseMarkdown(source);
      const page: Page = {
        sourcePath: relativeSource.split(path.sep).join('/'),
        outputPath: relativeSource.replace(/\.(md|markdown)$/i, '.html').split(path.sep).join('/'),
        title: titleFor(relativeSource, parsed.data),
        date: typeof parsed.data.date === 'string' ? parsed.data.date : undefined,
        tags: tagsFor(parsed.data),
        html: cached?.sourceHash === sourceHash && cached.markdownHtml !== undefined ? cached.markdownHtml : await marked.parse(parsed.content),
        frontmatter: parsed.data,
      };
      context.pages.push(page);
      (context.metadata.markdownContent ??= {}) as Record<string, string>;
      (context.metadata.markdownContent as Record<string, string>)[page.sourcePath] = parsed.content;
    }
    context.pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  }
}
