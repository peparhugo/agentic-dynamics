import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, relative, resolve } from 'node:path';
import { MarkdownPlugin } from './plugins/markdown';
import type { BuildContext, Plugin } from './plugins/plugin';
import { TemplatePlugin } from './plugins/template';
import { loadConfig } from './config';

export interface Page {
  sourcePath?: string;
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export type BuiltPages = Page[] & { stats: BuildStats };

interface CachedPage {
  sourceHash: string;
  templateHash: string;
  page: Page;
  renderedHtml: string;
  buildTimeMs: number;
}

interface BuildCache {
  version: 1;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Record<string, CachedPage>;
}

function markdownFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  });
}

function hashFile(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function templateHash(directory: string): string {
  if (!existsSync(directory)) return '';
  const files = readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return [path, ...templatePaths(path)];
    return entry.isFile() && /\.hbs$/i.test(entry.name) ? [path] : [];
  }).filter((path) => /\.hbs$/i.test(path)).sort();
  return createHash('sha256').update(files.map((path) => `${relative(directory, path)}\0${hashFile(path)}`).join('\0')).digest('hex');
}

function templatePaths(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? [path, ...templatePaths(path)] : [path];
  });
}

function readCache(path: string, context: BuildContext): BuildCache | undefined {
  if (!existsSync(path)) return undefined;
  try {
    const cache = JSON.parse(readFileSync(path, 'utf8')) as BuildCache;
    return cache.version === 1 && cache.contentDir === context.contentDir && cache.outputDir === context.outputDir && cache.templatesDir === context.templatesDir ? cache : undefined;
  } catch {
    return undefined;
  }
}

function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext, page?: Page): void {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    if (hook === 'onFile' && page) (handler as (file: Page, build: BuildContext) => void)(page, context);
    else (handler as (build: BuildContext) => void)(context);
  }
}

export function buildSite(options: BuildOptions = {}): BuiltPages {
  const config = loadConfig();
  const mergedOptions = { ...config, ...options, plugins: options.plugins ?? config.plugins };
  const context: BuildContext = {
    contentDir: resolve(mergedOptions.contentDir ?? 'content'),
    outputDir: resolve(mergedOptions.outputDir ?? 'dist'),
    templatesDir: resolve(mergedOptions.templatesDir ?? 'templates'),
    pages: []
  };
  if (!existsSync(context.contentDir)) throw new Error(`Content directory does not exist: ${context.contentDir}`);
  const cachePath = join(dirname(context.outputDir), '.ssg-cache.json');
  const cache = mergedOptions.incremental && !mergedOptions.clean ? readCache(cachePath, context) : undefined;
  const useCache = Boolean(cache);
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  const nextCache: BuildCache = { version: 1, contentDir: context.contentDir, outputDir: context.outputDir, templatesDir: context.templatesDir, pages: {} };
  const currentTemplateHash = templateHash(context.templatesDir);

  const plugins = [new MarkdownPlugin(), ...(mergedOptions.plugins ?? []), new TemplatePlugin()];
  runHook(plugins, 'onStart', context);
  try {
    if (!useCache || mergedOptions.clean || !mergedOptions.incremental) rmSync(context.outputDir, { recursive: true, force: true });
    mkdirSync(context.outputDir, { recursive: true });
    runHook(plugins, 'beforeBuild', context);
    for (const sourcePath of markdownFiles(context.contentDir)) {
      const sourceKey = relative(context.contentDir, sourcePath);
      const sourceHash = hashFile(sourcePath);
      const cached = cache?.pages[sourceKey];
      if (cached && cached.sourceHash === sourceHash && cached.templateHash === currentTemplateHash) {
        const page = { ...cached.page, sourcePath };
        if (!existsSync(page.outputPath)) {
          mkdirSync(dirname(page.outputPath), { recursive: true });
          writeFileSync(page.outputPath, cached.renderedHtml, 'utf8');
        }
        context.pages.push(page);
        nextCache.pages[sourceKey] = cached;
        stats.pagesSkipped += 1;
        stats.timeSavedMs += cached.buildTimeMs;
        continue;
      }
      const page: Page = { sourcePath, title: '', tags: [], outputPath: '', url: '', html: '' };
      const startedAt = Date.now();
      runHook(plugins, 'onFile', context, page);
      context.pages.push(page);
      nextCache.pages[sourceKey] = {
        sourceHash,
        templateHash: currentTemplateHash,
        page: { ...page, sourcePath: undefined },
        renderedHtml: readFileSync(page.outputPath, 'utf8'),
        buildTimeMs: Date.now() - startedAt
      };
      stats.pagesBuilt += 1;
    }
    context.pages.sort((left, right) => left.title.localeCompare(right.title));
    runHook(plugins, 'afterBuild', context);
    if (mergedOptions.incremental) {
      for (const [sourceKey, cached] of Object.entries(cache?.pages ?? {})) {
        if (!(sourceKey in nextCache.pages) && existsSync(cached.page.outputPath)) unlinkSync(cached.page.outputPath);
      }
      writeFileSync(cachePath, JSON.stringify(nextCache, null, 2), 'utf8');
    } else if (mergedOptions.clean && existsSync(cachePath)) {
      unlinkSync(cachePath);
    }
    for (const page of context.pages) delete page.sourcePath;
    Object.defineProperty(context.pages, 'stats', { value: stats });
    return context.pages as BuiltPages;
  } finally {
    runHook(plugins, 'onEnd', context);
  }
}

export type { BuildContext, Plugin } from './plugins/plugin';
