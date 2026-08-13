import { access, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join, relative, resolve, sep } from 'node:path';
import { loadPlugins } from './config.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildOptions, BuildPages, BuildStats, Page, Plugin, PluginContext } from './plugin.js';

export type { BuildOptions, BuildPages, BuildStats, Page, Plugin, PluginContext } from './plugin.js';

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  html: string;
}

interface BuildManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

const cacheFileName = '.ssg-cache.json';

async function readManifest(path: string): Promise<BuildManifest | undefined> {
  try {
    const manifest = JSON.parse(await readFile(path, 'utf8')) as BuildManifest;
    return manifest.version === 1 && manifest.pages ? manifest : undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function hashTemplates(directory: string): Promise<string> {
  const hash = createHash('sha256');
  async function visit(current: string): Promise<void> {
    let entries;
    try {
      entries = await readdir(current, { withFileTypes: true });
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
      throw error;
    }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const filePath = join(current, entry.name);
      if (entry.isDirectory()) await visit(filePath);
      else if (entry.name.endsWith('.hbs')) hash.update(relative(directory, filePath).split(sep).join('/')).update(await readFile(filePath));
    }
  }
  await visit(directory);
  return hash.digest('hex');
}

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

export async function buildSite(options: BuildOptions = {}): Promise<BuildPages> {
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
  const manifestPath = join(context.outputDirectory, cacheFileName);
  const incremental = options.incremental && !options.clean;
  const previousManifest = incremental ? await readManifest(manifestPath) : undefined;
  if (!incremental || !previousManifest) await rm(context.outputDirectory, { recursive: true, force: true });
  await mkdir(context.outputDirectory, { recursive: true });
  const templateHash = await hashTemplates(context.templatesDirectory);
  const nextManifest: BuildManifest = { version: 1, pages: {} };
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  const buildStartedAt = Date.now();
  for (const page of context.pages) {
    const cached = previousManifest?.pages[page.slug];
    const target = join(context.outputDirectory, `${page.slug}.html`);
    const outputExists = await access(target).then(() => true, () => false);
    if (cached && outputExists && cached.sourceHash === page.sourceHash && cached.templateHash === templateHash) {
      nextManifest.pages[page.slug] = cached;
      stats.pagesSkipped += 1;
      continue;
    }
    context.page = page;
    context.html = undefined;
    await runFileHooks(plugins, page, context);
    if (context.html !== undefined) {
      await mkdir(join(target, '..'), { recursive: true });
      await writeFile(target, context.html, 'utf8');
      nextManifest.pages[page.slug] = { sourceHash: page.sourceHash ?? '', templateHash, html: context.html };
      stats.pagesBuilt += 1;
    }
  }
  if (previousManifest) {
    await Promise.all(Object.keys(previousManifest.pages)
      .filter((slug) => !nextManifest.pages[slug])
      .map((slug) => rm(join(context.outputDirectory, `${slug}.html`), { force: true })));
  }
  await writeFile(join(context.outputDirectory, 'index.html'), renderIndex(context.pages), 'utf8');
  await writeFile(manifestPath, JSON.stringify(nextManifest, null, 2), 'utf8');
  const elapsedMs = Math.max(Date.now() - buildStartedAt, 1);
  stats.timeSavedMs = stats.pagesSkipped === 0 ? 0 : Math.round((elapsedMs / Math.max(stats.pagesBuilt, 1)) * stats.pagesSkipped);
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return Object.assign(context.pages, { buildStats: stats });
}
