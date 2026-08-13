import { access, mkdir, readdir, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join, relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildContext, Plugin } from './plugin.js';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
  sourcePath?: string;
  sourceHash?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configPath?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface ResolvedBuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}

interface CacheManifest {
  version: 1;
  templateHash: string;
  pages: Record<string, { sourceHash: string; output: string }>;
}

const CACHE_FILE = '.ssg-cache.json';

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map(async (entry) => {
      const file = join(directory, entry.name);
      return entry.isDirectory() ? filesIn(file) : [file];
    }))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function hashTemplates(directory: string): Promise<string> {
  const files = await filesIn(directory);
  const hash = createHash('sha256');
  for (const file of files.sort()) hash.update(`${relative(directory, file)}\0${await readFile(file)}`);
  return hash.digest('hex');
}

async function readManifest(path: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await readFile(path, 'utf8')) as CacheManifest;
    return manifest.version === 1 ? manifest : undefined;
  } catch (error: unknown) {
    if (error instanceof SyntaxError || (error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function configuredPlugins(configPath: string): Promise<Plugin[]> {
  const path = resolve(configPath);
  try { await access(path); } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const config = await import(pathToFileURL(path).href) as { default?: SsgConfig; plugins?: Plugin[] };
  return config.default?.plugins ?? config.plugins ?? [];
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, ...args: unknown[]): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook] as ((...hookArgs: unknown[]) => void | Promise<void>) | undefined;
    if (handler) await handler.apply(plugin, args);
  }
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<BuildResult> {
  const startedAt = performance.now();
  const resolved: ResolvedBuildOptions = {
    contentDir: options.contentDir ?? './content',
    outputDir: options.outputDir ?? './dist',
    templatesDir: options.templatesDir ?? './templates',
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...await configuredPlugins(options.configPath ?? './ssg.config.ts'), ...(options.plugins ?? [])];
  const cachePath = join(resolved.outputDir, CACHE_FILE);
  const manifest = options.clean ? undefined : await readManifest(cachePath);
  const incremental = options.incremental === true && manifest !== undefined;
  const context: BuildContext = { options: resolved, pages: [], incremental, changedSlugs: new Set() };

  await runHook(plugins, 'onStart', context);
  if (!incremental) await rm(resolved.outputDir, { recursive: true, force: true });
  await mkdir(resolved.outputDir, { recursive: true });
  await runHook(plugins, 'beforeBuild', context);
  const templateHash = await hashTemplates(resolved.templatesDir);
  for (const page of context.pages) {
    const cached = page.sourcePath ? manifest?.pages[page.sourcePath] : undefined;
    const changed = !incremental || !cached || cached.sourceHash !== page.sourceHash || manifest?.templateHash !== templateHash;
    if (changed) context.changedSlugs.add(page.slug);
  }
  for (const page of context.pages) if (context.changedSlugs.has(page.slug)) await runHook(plugins, 'onFile', page, context);
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  const currentSources = new Set(context.pages.flatMap((page) => page.sourcePath ? [page.sourcePath] : []));
  if (incremental) for (const [source, cached] of Object.entries(manifest?.pages ?? {})) {
    if (!currentSources.has(source)) await unlink(join(resolved.outputDir, cached.output)).catch((error: unknown) => {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    });
  }
  const cache: CacheManifest = { version: 1, templateHash, pages: {} };
  for (const page of context.pages) if (page.sourcePath && page.sourceHash) {
    cache.pages[page.sourcePath] = { sourceHash: page.sourceHash, output: `${page.slug}.html` };
  }
  await writeFile(cachePath, JSON.stringify(cache, null, 2));
  const pagesBuilt = context.changedSlugs.size;
  const elapsedMs = performance.now() - startedAt;
  return { pages: context.pages, stats: { pagesBuilt, pagesSkipped: context.pages.length - pagesBuilt, timeSavedMs: pagesBuilt ? Math.round(elapsedMs * (context.pages.length - pagesBuilt) / pagesBuilt) : Math.round(elapsedMs) } };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(options)).pages;
}
