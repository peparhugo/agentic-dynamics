import path from 'node:path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import { parse as parseYaml } from 'yaml';
import type { Frontmatter, Page } from '../index.js';
import type { Plugin } from '../plugin.js';

const markdown = new MarkdownIt({ html: false });
const pageCache = new Map<string, { source: string; page: Page }>();

function renderMarkdown(source: string): string {
  const embeddedHtml: string[] = [];
  const codePattern = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`+[^`\n]*`+)/g;
  const tokenized = source.split(codePattern).map((segment, index) => {
    if (index % 2 === 1) return segment;
    return segment.replace(/<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>/g, (tag) => {
      const token = `SSGRAWHTMLTOKEN${embeddedHtml.length}ENDTOKEN`;
      embeddedHtml.push(tag);
      return token;
    });
  }).join('');
  const rendered = markdown.render(tokenized);
  return rendered.replace(/SSGRAWHTMLTOKEN(\d+)ENDTOKEN/g, (_token, index: string) =>
    embeddedHtml[Number(index)] ?? '');
}

function parseFrontmatter(source: string): { content: string; data: Frontmatter } {
  const parsed = matter(source, {
    engines: {
      yaml: (text: string): Record<string, unknown> =>
        parseYaml(text, { schema: 'failsafe' }) as Record<string, unknown>,
    },
  });
  const raw = parsed.data as Record<string, unknown>;
  const tags = Array.isArray(raw.tags)
    ? raw.tags.map(String)
    : typeof raw.tags === 'string'
      ? raw.tags.split(',').map((tag) => tag.trim()).filter(Boolean)
      : [];
  return {
    content: parsed.content,
    data: {
      ...raw,
      title: typeof raw.title === 'string' ? raw.title : undefined,
      date: typeof raw.date === 'string' ? raw.date : undefined,
      tags,
      template: typeof raw.template === 'string' ? raw.template : undefined,
      layout: raw.layout === false || raw.layout === 'false'
        ? false
        : typeof raw.layout === 'string' ? raw.layout : undefined,
    },
  };
}

export function parseMarkdownPage(source: string, sourcePath: string): Page {
  const cached = pageCache.get(sourcePath);
  if (cached?.source === source) {
    return { ...cached.page, tags: [...cached.page.tags], data: cached.page.data ? { ...cached.page.data } : undefined };
  }
  const { content, data } = parseFrontmatter(source);
  const baseName = path.basename(sourcePath, path.extname(sourcePath));
  const title = data.title ?? baseName;
  const page: Page = {
    title,
    date: data.date,
    tags: data.tags ?? [],
    sourcePath,
    outputName: `${baseName === 'index' ? 'index-page' : baseName}.html`,
    html: renderMarkdown(content),
    template: data.template,
    layout: data.layout,
    data: { ...data, title },
  };
  pageCache.set(sourcePath, { source, page });
  return { ...page, tags: [...page.tags], data: page.data ? { ...page.data } : undefined };
}

export class MarkdownPlugin implements Plugin {
  onFile(page: Page): void {
    if (page.source === undefined) return;
    Object.assign(page, parseMarkdownPage(page.source, page.sourcePath));
    delete page.source;
  }
}
