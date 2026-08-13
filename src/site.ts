import { promises as fs } from 'node:fs';
import path from 'node:path';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import { runHook, type BuildContext, type Plugin } from './plugin.js';
import { loadPlugins } from './config.js';

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character] ?? character);
}

export function renderPage(page: Page): string {
  const details = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <main>
    <a href="/index.html">Home</a>
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${details}
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
${items}
    </ul>
  </main>
</body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: BuildContext = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    pages: [],
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...(options.plugins ?? await loadPlugins())];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  await fs.rm(context.outputDir, { recursive: true, force: true });
  await fs.mkdir(context.outputDir, { recursive: true });
  for (const page of context.pages) await runHook(plugins, 'onFile', page, context);
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return context.pages;
}
