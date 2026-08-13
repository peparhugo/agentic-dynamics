import { mkdir, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { loadPlugins } from './config.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildOptions, Page, Plugin, PluginContext } from './plugin.js';

export type { BuildOptions, Page, Plugin, PluginContext } from './plugin.js';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `<li><a href="/${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${links}</ul></main></body>
</html>
`;
}

async function runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (handler) await handler(context);
  }
}

async function runFileHooks(plugins: Plugin[], page: Page, context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    if (plugin.onFile) await plugin.onFile(page, context);
  }
}

export async function readPages(contentDirectory: string): Promise<Page[]> {
  const context: PluginContext = { options: { content: contentDirectory }, contentDirectory, outputDirectory: '', templatesDirectory: '', pages: [] };
  await new MarkdownPlugin().beforeBuild?.(context);
  return context.pages;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: PluginContext = {
    options,
    contentDirectory: resolve(options.content ?? 'content'),
    outputDirectory: resolve(options.output ?? 'dist'),
    templatesDirectory: resolve(options.templates ?? 'templates'),
    pages: [],
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...await loadPlugins()];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  await rm(context.outputDirectory, { recursive: true, force: true });
  await mkdir(context.outputDirectory, { recursive: true });
  for (const page of context.pages) {
    context.page = page;
    context.html = undefined;
    await runFileHooks(plugins, page, context);
    if (context.html !== undefined) {
      const target = join(context.outputDirectory, `${page.slug}.html`);
      await mkdir(join(target, '..'), { recursive: true });
      await writeFile(target, context.html, 'utf8');
    }
  }
  await writeFile(join(context.outputDirectory, 'index.html'), renderIndex(context.pages), 'utf8');
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return context.pages;
}
