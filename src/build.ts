import * as fs from 'fs';
import * as path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page } from './types';
import { pageTemplate, indexTemplate } from './template';

function normalizeDate(d: unknown): string | undefined {
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  if (typeof d === 'string') return d;
  return undefined;
}

function normalizeTags(t: unknown): string[] | undefined {
  if (Array.isArray(t)) return t.map((v) => String(v));
  return undefined;
}

export function build(contentDir: string, outputDir: string): void {
  const absoluteContent = path.resolve(contentDir);

  if (!fs.existsSync(absoluteContent)) {
    throw new Error(`Content directory does not exist: ${absoluteContent}`);
  }

  const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));

  const pages: Page[] = [];

  for (const file of files) {
    const filePath = path.join(absoluteContent, file);
    const slug = path.basename(file, '.md');
    const raw = matter.read(filePath);
    const html = marked.parse(raw.content) as string;

    const page: Page = {
      slug,
      title: String(raw.data.title || slug),
      date: normalizeDate(raw.data.date),
      tags: normalizeTags(raw.data.tags),
      content: raw.content,
      html,
    };

    pages.push(page);
  }

  pages.sort((a, b) => {
    if (a.date && b.date) {
      return b.date.localeCompare(a.date);
    }
    if (a.date) return -1;
    if (b.date) return 1;
    return a.title.localeCompare(b.title);
  });

  const absoluteOutput = path.resolve(outputDir);
  if (!fs.existsSync(absoluteOutput)) {
    fs.mkdirSync(absoluteOutput, { recursive: true });
  }

  for (const page of pages) {
    const html = pageTemplate(page);
    fs.writeFileSync(path.join(absoluteOutput, `${page.slug}.html`), html);
  }

  const indexHtml = indexTemplate(pages);
  fs.writeFileSync(path.join(absoluteOutput, 'index.html'), indexHtml);
}
