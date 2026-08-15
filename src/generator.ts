import fs from 'node:fs/promises';
import path from 'node:path';
import { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildCache, BuildContext, BuildState, Plugin, PluginFactory } from './plugin';

export type { BuildCache, BuildContext, BuildState, Plugin, PluginFactory } from './plugin';

export interface Frontmatter { title?: string; date?: string; tags?: string[]; [key: string]: unknown; }
export interface Page { slug: string; source: string; title: string; date?: string; tags: string[]; html: string; template?: string; layout?: string; }

async function loadConfiguredPlugins(): Promise<Plugin[]> {
  const configPath = path.resolve('ssg.config.ts');
  try { await fs.access(configPath); } catch { return []; }
  // TypeScript configs are transpiled by ts-jest in tests and by the project's build workflow.
  const loaded = await import(configPath);
  const configured = loaded.default ?? loaded.plugins ?? loaded;
  const values: PluginFactory[] = Array.isArray(configured) ? configured : configured.plugins ?? [];
  return Promise.all(values.map(async (factory) => typeof factory === 'function' ? factory() : factory));
}

export interface BuildOptions { incremental?: boolean; clean?: boolean; }
export interface BuildStats { pagesBuilt: number; pagesSkipped: number; timeSavedMs: number; }
export interface BuildResult { pages: Page[]; stats: BuildStats; }

function emptyCache(): BuildCache { return { version: 1, templateHash: '', pages: {} }; }

async function readCache(cachePath: string, clean: boolean): Promise<BuildCache> {
  if (clean) return emptyCache();
  try {
    const parsed = JSON.parse(await fs.readFile(cachePath, 'utf8')) as Partial<BuildCache>;
    if (parsed.version !== 1 || !parsed.pages || typeof parsed.pages !== 'object') return emptyCache();
    return { version: 1, templateHash: parsed.templateHash ?? '', pages: parsed.pages as BuildCache['pages'] };
  } catch { return emptyCache(); }
}

export async function buildSiteWithStats(contentDir = './content', outputDir = './dist', templatesDir = './templates', options: BuildOptions = {}): Promise<BuildResult> {
  const cachePath = path.join(outputDir, '.ssg-cache.json');
  const cache = await readCache(cachePath, options.clean === true);
  const build: BuildState = { incremental: options.incremental === true, clean: options.clean === true, cache, cachePath, builtSources: new Set(), skippedSources: new Set(), sourceHashes: new Map(), templateHash: '', timeSavedMs: 0, pageTimes: new Map(), parsedPages: new Map() };
  const context: BuildContext = { contentDir, outputDir, templatesDir, pages: [], files: [], data: new Map(), build };
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(), ...(await loadConfiguredPlugins())];
  for (const plugin of plugins) await plugin.onStart?.(context);
  for (const plugin of plugins) await plugin.beforeBuild?.(context);
  for (let index = 0; index < context.pages.length; index += 1) {
    let page = context.pages[index];
    if (build.skippedSources.has(page.source)) {
      const cached = cache.pages[page.source];
      if (cached?.page) context.pages[index] = cached.page;
      continue;
    }
    for (const plugin of plugins) { const result = await plugin.onFile?.(page, context); if (result) page = result; }
    context.pages[index] = page;
  }
  for (const plugin of plugins) await plugin.afterBuild?.(context);
  for (const plugin of plugins) await plugin.onEnd?.(context);
  const nextCache: BuildCache = { version: 1, templateHash: build.templateHash, pages: {} };
  for (const page of context.pages) {
    const sourceHash = build.sourceHashes.get(page.source);
    if (!sourceHash) continue;
    const previous = cache.pages[page.source];
    nextCache.pages[page.source] = { sourceHash, templateHash: build.templateHash, page, parsedPage: build.parsedPages.get(page.source) ?? previous?.parsedPage, buildTimeMs: build.builtSources.has(page.source) ? (build.pageTimes.get(page.source) ?? 0) : (previous?.buildTimeMs ?? 0) };
  }
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(cachePath, JSON.stringify(nextCache, null, 2));
  return { pages: context.pages, stats: { pagesBuilt: build.builtSources.size, pagesSkipped: build.skippedSources.size, timeSavedMs: Math.round(build.timeSavedMs) } };
}

export async function buildSite(contentDir = './content', outputDir = './dist', templatesDir = './templates', options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(contentDir, outputDir, templatesDir, options)).pages;
}

export { parseMarkdown } from './plugins/markdown';
