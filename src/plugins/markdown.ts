import * as fs from 'fs';
import { parseMarkdown } from '../markdown';
import { Page, Plugin } from '../plugin';

function normalizeDate(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  const str = String(value).trim();
  return str.length > 0 ? str : null;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((v) => String(v).trim()).filter((v) => v.length > 0);
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }
  return [];
}

function normalizeName(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): void {
    const raw = fs.readFileSync(page.sourcePath, 'utf8');
    const { frontmatter, html } = parseMarkdown(raw);

    const rawTitle = frontmatter.title;
    const title =
      typeof rawTitle === 'string' && rawTitle.trim().length > 0
        ? rawTitle.trim()
        : page.slug;

    page.frontmatter = frontmatter;
    page.html = html;
    page.title = title;
    page.date = normalizeDate(frontmatter.date);
    page.tags = normalizeTags(frontmatter.tags);
    page.template = normalizeName(frontmatter.template);
    page.layout = normalizeName(frontmatter.layout);
  }
}
