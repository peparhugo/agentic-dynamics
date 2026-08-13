import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadConfig } from './config.js';
import type { Plugin } from './plugin.js';
import { MarkdownPlugin, parseMarkdownPage } from './plugins/markdown.js';
import { renderedPage, TemplatePlugin, type RenderedPage } from './plugins/template.js';

export type { Plugin, PluginHook, SsgConfig } from './plugin.js';
export { MarkdownPlugin } from './plugins/markdown.js';
export { TemplatePlugin } from './plugins/template.js';
export { DevServerPlugin } from './plugins/dev-server.js';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string | false;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputName: string;
  html: string;
  template?: string;
  layout?: string | false;
  data?: Frontmatter;
  /** Raw input available to file plugins until MarkdownPlugin processes it. */
  source?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface SsgEngine {
  build(): Promise<Page[]>;
  close(): Promise<void>;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC',
  }).format(date);
}

function document(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

export function parsePage(source: string, sourcePath: string): Page {
  return parseMarkdownPage(source, sourcePath);
}

export function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return document(page.title, `<main>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${metadata}
    ${page.html}
  </article>
</main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '';
    return `    <li><a href="${encodeURIComponent(page.outputName)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, page?: Page): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (typeof handler === 'function') {
      await (handler as (page?: Page) => void | Promise<void>).call(plugin, page);
    }
  }
}

export function createSsg(options: BuildOptions = {}): SsgEngine {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const configured = options.plugins ?? loadConfig(options.configFile).plugins ?? [];
  const plugins: Plugin[] = [new MarkdownPlugin(), ...configured, new TemplatePlugin(templatesDir)];
  let started = false;
  let closed = false;

  return {
    async build(): Promise<Page[]> {
      if (closed) throw new Error('SSG engine is closed');
      if (!started) {
        await runHook(plugins, 'onStart');
        started = true;
      }
      await runHook(plugins, 'beforeBuild');
      const entries = await fs.readdir(contentDir, { withFileTypes: true });
      const markdownFiles = entries
        .filter((entry) => entry.isFile() && /\.md$/i.test(entry.name))
        .map((entry) => entry.name)
        .sort();
      const pages: Page[] = markdownFiles.map((fileName) => ({
        title: path.basename(fileName, path.extname(fileName)),
        tags: [],
        sourcePath: path.join(contentDir, fileName),
        outputName: '',
        html: '',
      }));
      for (const page of pages) {
        page.source = await fs.readFile(page.sourcePath, 'utf8');
        await runHook(plugins, 'onFile', page);
      }
      pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.title.localeCompare(b.title));
      await fs.mkdir(outputDir, { recursive: true });
      await Promise.all(pages.map((page) => fs.writeFile(
        path.join(outputDir, page.outputName),
        (page as RenderedPage)[renderedPage] ?? renderPage(page),
        'utf8',
      )));
      await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
      await runHook(plugins, 'afterBuild');
      return pages;
    },
    async close(): Promise<void> {
      if (closed) return;
      closed = true;
      if (started) await runHook(plugins, 'onEnd');
    },
  };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const ssg = createSsg(options);
  try {
    return await ssg.build();
  } finally {
    await ssg.close();
  }
}
