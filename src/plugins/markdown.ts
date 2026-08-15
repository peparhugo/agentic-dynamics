import fs from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { hashContent } from '../hash';
import type { Frontmatter, Page } from '../generator';
import type { BuildContext, Plugin } from '../plugin';

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) return trimmed.slice(1, -1).split(',').map((item) => item.trim()).filter(Boolean);
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) return trimmed.slice(1, -1);
  return trimmed;
}

function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } | undefined {
  if (!source.startsWith('---')) return undefined;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?/);
  if (!match) return undefined;
  if (match[1].trim().startsWith('{')) {
    const parsed = matter(source);
    return { data: parsed.data as Frontmatter, content: parsed.content };
  }
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (key) data[key] = parseScalar(line.slice(separator + 1));
  }
  return { data, content: source.slice(match[0].length) };
}

export function parseMarkdown(source: string, sourcePath = 'page.md'): Page {
  const yaml = parseYamlFrontmatter(source);
  const parsed = yaml ? { data: yaml.data, content: matter(yaml.content).content } : matter(source);
  const data = parsed.data as Frontmatter;
  const basename = path.basename(sourcePath, path.extname(sourcePath));
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : data.tags ? String(data.tags).split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    slug: basename,
    source: sourcePath,
    title: data.title ? String(data.title) : basename,
    date: data.date ? String(data.date) : undefined,
    tags,
    template: data.template ? String(data.template) : undefined,
    layout: data.layout ? String(data.layout) : undefined,
    html: String(marked.parse(parsed.content)),
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(fullPath));
    else if (/\.md$/i.test(entry.name)) files.push(fullPath);
  }
  return files.sort();
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  async beforeBuild(context: BuildContext): Promise<void> {
    context.files = await markdownFiles(context.contentDir);
    context.pages = await Promise.all(context.files.map(async (file) => {
      const source = await fs.readFile(file, 'utf8');
      const relative = path.relative(context.contentDir, file).split(path.sep).join('/');
      const sourceHash = hashContent(source);
      context.build?.sourceHashes.set(relative, sourceHash);
      const cached = context.build?.cache.pages[relative];
      const page = cached?.sourceHash === sourceHash && cached.parsedPage ? cached.parsedPage : parseMarkdown(source, relative);
      context.build?.parsedPages.set(relative, page);
      return page;
    }));
    context.pages.sort((a, b) => (b.date || '').localeCompare(a.date || '') || a.title.localeCompare(b.title));
  }
}
