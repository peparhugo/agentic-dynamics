import fs from 'fs';
import path from 'path';
import { loadConfig } from './config';
import { SSGEngine, findMarkdownFiles, resolveTemplateName } from './engine';
import { PluginContext } from './plugin';
import { Page } from './types';
import { hashString } from './hash';
import { parseFrontmatterCached } from './frontmatter';
import {
  CACHE_VERSION,
  CacheManifest,
  PageCacheEntry,
  defaultCacheFile,
  emptyCacheManifest,
  hashPartials,
  hashTemplate,
  loadCacheManifest,
  saveCacheManifest,
} from './cache';

export { findMarkdownFiles };

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export interface IncrementalBuildOptions extends BuildOptions {
  /** Ignore any existing cache and rebuild every page, e.g. when `.ssg-cache.json` is missing or stale. */
  clean?: boolean;
  /** Path to the incremental-build manifest. Defaults to `.ssg-cache.json` in the current working directory. */
  cacheFile?: string;
}

export interface BuildStats {
  total: number;
  built: number;
  skipped: number;
  timeMs: number;
  timeSavedMs: number;
}

export interface IncrementalBuildResult extends BuildResult {
  stats: BuildStats;
}

export function defaultTemplatesDir(): string {
  return path.resolve(process.cwd(), 'templates');
}

export function buildPage(contentDir: string, filename: string, templatesDir: string = defaultTemplatesDir()): Page {
  const engine = new SSGEngine(loadConfig(process.cwd()).plugins);
  const ctx: PluginContext = { contentDir, templatesDir };
  return engine.buildFile(contentDir, filename, ctx);
}

/**
 * Runs a full build pass through the plugin pipeline and writes the
 * resulting pages to `ctx.outputDir`. Shared by the one-shot `build()` below
 * and by the dev server, which reruns it on every watched file change using
 * the same engine instance (so plugins like the dev server's own reload
 * broadcast fire on every pass).
 */
export function buildAndWrite(engine: SSGEngine, ctx: PluginContext): Page[] {
  const outputDir = ctx.outputDir;
  if (!outputDir) {
    throw new Error('outputDir is required to write build output');
  }
  fs.mkdirSync(outputDir, { recursive: true });
  const pages = engine.runBuild(ctx);
  for (const page of pages) {
    fs.writeFileSync(path.join(outputDir, page.outputPath), page.html, 'utf-8');
  }
  return pages;
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir, templatesDir = defaultTemplatesDir() } = options;
  const engine = new SSGEngine(loadConfig(process.cwd()).plugins);
  const ctx: PluginContext = { contentDir, outputDir, templatesDir };
  const pages = buildAndWrite(engine, ctx);
  return { pages, outputDir };
}

/**
 * Incremental build pass: pages whose source and resolved template are both
 * unchanged since the last run (per `.ssg-cache.json`) are skipped entirely —
 * no re-parse, re-render, or re-write — and their previously built `Page` is
 * reused so the plugin pipeline (e.g. the index page) still sees every page.
 * A missing/corrupt cache or `clean: true` falls back to building everything,
 * exactly like a first run.
 */
export function buildIncremental(options: IncrementalBuildOptions): IncrementalBuildResult {
  const {
    contentDir,
    outputDir,
    templatesDir = defaultTemplatesDir(),
    clean = false,
    cacheFile = defaultCacheFile(process.cwd()),
  } = options;

  const startedAt = Date.now();
  fs.mkdirSync(outputDir, { recursive: true });

  const engine = new SSGEngine(loadConfig(process.cwd()).plugins);
  const ctx: PluginContext = { contentDir, outputDir, templatesDir };
  engine.runBeforeBuild(ctx);

  const previous: CacheManifest = clean ? emptyCacheManifest() : loadCacheManifest(cacheFile);
  const partialsHash = hashPartials(templatesDir);
  const templateHashCache = new Map<string, string>();
  const templateHashFor = (templateName: string): string => {
    let hash = templateHashCache.get(templateName);
    if (!hash) {
      hash = hashTemplate(templatesDir, templateName, partialsHash);
      templateHashCache.set(templateName, hash);
    }
    return hash;
  };

  const files = findMarkdownFiles(contentDir);
  const pages: Page[] = [];
  const nextCachePages: Record<string, PageCacheEntry> = {};
  let built = 0;
  let skipped = 0;
  let builtTimeMs = 0;

  for (const file of files) {
    const raw = fs.readFileSync(path.join(contentDir, file), 'utf-8');
    const sourceHash = hashString(raw);
    const { data } = parseFrontmatterCached(sourceHash, raw);
    const templateHash = templateHashFor(resolveTemplateName(data));

    const cachedEntry = previous.pages[file];
    const outputStillExists = !!cachedEntry && fs.existsSync(path.join(outputDir, cachedEntry.page.outputPath));

    if (
      cachedEntry &&
      outputStillExists &&
      cachedEntry.sourceHash === sourceHash &&
      cachedEntry.templateHash === templateHash
    ) {
      pages.push(cachedEntry.page);
      nextCachePages[file] = cachedEntry;
      skipped += 1;
      continue;
    }

    const pageStartedAt = Date.now();
    const page = engine.buildFile(contentDir, file, ctx);
    fs.writeFileSync(path.join(outputDir, page.outputPath), page.html, 'utf-8');
    builtTimeMs += Date.now() - pageStartedAt;
    built += 1;

    pages.push(page);
    nextCachePages[file] = { sourceHash, templateHash, page };
  }

  engine.runAfterBuild(pages, ctx);

  const avgPageBuildMs = built > 0 ? builtTimeMs / built : previous.avgPageBuildMs;
  const timeSavedMs = Math.round(skipped * avgPageBuildMs);

  saveCacheManifest(cacheFile, { version: CACHE_VERSION, avgPageBuildMs, pages: nextCachePages });

  const stats: BuildStats = {
    total: files.length,
    built,
    skipped,
    timeMs: Date.now() - startedAt,
    timeSavedMs,
  };

  return { pages, outputDir, stats };
}
