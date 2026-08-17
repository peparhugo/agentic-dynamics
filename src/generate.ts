import { promises as fs } from 'fs';
import path from 'path';
import { extractFrontmatter } from './frontmatter';
import { renderMarkdown } from './markdown';
import { createTemplateEngine } from './engine';
import type { Page } from './types';

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export async function listMarkdownFiles(dir: string): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await listMarkdownFiles(full)));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

function toTitle(slug: string): string {
  const base = path.basename(slug);
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export async function readPage(filePath: string, contentDir: string): Promise<Page> {
  const source = await fs.readFile(filePath, 'utf8');
  const { frontmatter, content } = extractFrontmatter(source);
  const rel = path.relative(contentDir, filePath).split(path.sep).join('/');
  const slug = rel.replace(/\.md$/i, '');
  const title = frontmatter.title || toTitle(slug);
  return {
    slug,
    title,
    date: frontmatter.date,
    tags: frontmatter.tags,
    html: renderMarkdown(content),
    template: frontmatter.template,
    layout: frontmatter.layout,
  };
}

function comparePages(a: Page, b: Page): number {
  const da = a.date ? Date.parse(a.date) : NaN;
  const db = b.date ? Date.parse(b.date) : NaN;
  const daValid = !Number.isNaN(da);
  const dbValid = !Number.isNaN(db);

  if (daValid && dbValid) {
    if (da !== db) {
      return db - da;
    }
  } else if (daValid) {
    return -1;
  } else if (dbValid) {
    return 1;
  }
  return a.title.localeCompare(b.title);
}

export async function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = './templates'
): Promise<BuildResult> {
  const files = await listMarkdownFiles(contentDir);

  const pages: Page[] = [];
  for (const file of files) {
    pages.push(await readPage(file, contentDir));
  }
  pages.sort(comparePages);

  const engine = await createTemplateEngine(templatesDir);

  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), engine.renderIndex(pages), 'utf8');

  for (const page of pages) {
    const outPath = path.join(outputDir, `${page.slug}.html`);
    await fs.mkdir(path.dirname(outPath), { recursive: true });
    await fs.writeFile(outPath, engine.renderPage(page), 'utf8');
  }

  return { pages, outputDir };
}
