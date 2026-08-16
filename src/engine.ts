/**
 * The core SSG engine.
 *
 * The engine orchestrates the plugin pipeline. Each build runs the plugin
 * lifecycle in order:
 *
 *   onStart -> beforeBuild -> (onFile per page) -> afterBuild -> onEnd
 *
 * The engine is responsible for loading pages, running the pipeline, and
 * writing the generated HTML (each page plus the site index) to disk.
 *
 * When the `incremental` option is set, the engine consults the on-disk cache
 * manifest and skips any page whose source and template hashes are unchanged,
 * reusing its previously rendered HTML and parsed page (frontmatter included).
 */

import fs from 'fs';
import path from 'path';

import { performance } from 'perf_hooks';

import {
  CACHE_VERSION,
  computeTemplateHash,
  cacheFilePath,
  hashContent,
  hashFile,
  loadCache,
  saveCache,
} from './cache';
import type { BuildStats, CacheManifest } from './cache';
import { loadConfig, loadPlugins } from './config';
import { listMarkdownFiles, loadPages, readPage, slugify } from './load';
import { PluginPipeline } from './plugin';
import { renderIndex, renderPage } from './render';
import type { Plugin, PluginContext } from './plugin';
import type { BuildOptions, Page } from './types';

/** Options accepted by the engine (a superset of the public build options). */
export interface EngineOptions extends BuildOptions {
  /** Path to the SSG config file. */
  config?: string;
  /** Extra plugins registered after the config file plugins. */
  plugins?: Plugin[];
}

/**
 * Orchestrates the plugin pipeline for a single build. Create one with
 * {@link createEngine} and drive it with {@link SSGEngine.run}, or call
 * the individual lifecycle stages (`start`, `build`, `finish`) directly.
 */
export class SSGEngine {
  /** The plugin pipeline driving every registered plugin. */
  readonly pipeline: PluginPipeline;
  /** Shared state available to every plugin hook. */
  readonly context: PluginContext;
  /** Options for this build. */
  readonly options: EngineOptions;
  /** Statistics from the most recent build. */
  readonly stats: BuildStats = {
    pagesBuilt: 0,
    pagesSkipped: 0,
    timeSavedMs: 0,
    totalMs: 0,
    cacheLoaded: false,
  };

  constructor(plugins: Plugin[], context: PluginContext, options: EngineOptions) {
    this.pipeline = new PluginPipeline(plugins);
    this.context = context;
    this.options = options;
  }

  /** Run the `onStart` hooks. */
  start(): void {
    this.pipeline.onStart(this.context);
  }

  /**
   * Load the pages, run the pipeline and write every generated HTML file.
   * Returns the built pages.
   */
  build(): Page[] {
    const { outputDir, clean } = this.options;
    fs.mkdirSync(outputDir, { recursive: true });

    if (clean) {
      this.removeCache();
    }

    return this.options.incremental ? this.buildIncremental() : this.buildFull();
  }

  /** Run the `onEnd` hooks. */
  finish(): void {
    this.pipeline.onEnd(this.context);
  }

  /** Run the full lifecycle: `start`, `build`, `finish`. */
  run(): Page[] {
    this.start();
    const pages = this.build();
    this.finish();
    return pages;
  }

  /** Delete the cache manifest for this build's output directory, if any. */
  private removeCache(): void {
    const cachePath = cacheFilePath(this.options.outputDir);
    if (fs.existsSync(cachePath)) {
      fs.rmSync(cachePath);
    }
  }

  /** Rebuild every page from scratch (the default, non-incremental build). */
  private buildFull(): Page[] {
    const { contentDir, outputDir } = this.options;
    const started = performance.now();

    this.pipeline.beforeBuild(this.context);

    const pages = loadPages(contentDir);
    this.context.pages = pages;

    for (const page of pages) {
      this.pipeline.onFile(page, this.context);
      const html = this.context.outputs[page.outputName] ?? renderPage(page);
      fs.writeFileSync(path.join(outputDir, page.outputName), html);
    }

    this.pipeline.afterBuild(this.context);

    const indexHtml = this.context.outputs['index.html'] ?? renderIndex(pages);
    this.context.outputs['index.html'] = indexHtml;
    fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);

    this.stats.pagesBuilt = pages.length;
    this.stats.pagesSkipped = 0;
    this.stats.timeSavedMs = 0;
    this.stats.cacheLoaded = false;
    this.stats.totalMs = performance.now() - started;

    return pages;
  }

  /**
   * Incremental build: reuse any page whose source and template hashes match
   * the cache manifest, rebuilding only the pages that changed. The refreshed
   * manifest is written back so the next build can skip even more work.
   */
  private buildIncremental(): Page[] {
    const { contentDir, outputDir } = this.options;
    const stats = this.stats;
    const started = performance.now();

    const cachePath = cacheFilePath(outputDir);
    const manifest = loadCache(cachePath);
    stats.cacheLoaded = manifest !== null;

    const templateHash = computeTemplateHash(this.options.templatesDir);
    const newManifest: CacheManifest = { version: CACHE_VERSION, entries: {} };
    const pages: Page[] = [];
    const sourceHashes: string[] = [];

    this.pipeline.beforeBuild(this.context);

    for (const fileName of listMarkdownFiles(contentDir)) {
      const sourcePath = path.join(contentDir, fileName);
      const sourceHash = hashFile(sourcePath);
      const outputName = `${slugify(fileName)}.html`;
      const cached = manifest?.entries[outputName];
      sourceHashes.push(sourceHash);

      if (
        cached &&
        cached.page &&
        cached.sourceHash === sourceHash &&
        cached.templateHash === templateHash
      ) {
        pages.push(restorePage(cached.page));
        this.context.outputs[outputName] = cached.output;
        const outputPath = path.join(outputDir, outputName);
        if (!fs.existsSync(outputPath)) {
          fs.writeFileSync(outputPath, cached.output);
        }
        stats.pagesSkipped += 1;
        stats.timeSavedMs += cached.buildMs;
        newManifest.entries[outputName] = cached;
        continue;
      }

      const buildStart = performance.now();
      const page = readPage(fileName, contentDir);
      pages.push(page);
      this.pipeline.onFile(page, this.context);
      const html = this.context.outputs[page.outputName] ?? renderPage(page);
      fs.writeFileSync(path.join(outputDir, page.outputName), html);

      newManifest.entries[page.outputName] = {
        sourceHash,
        templateHash,
        page: clonePage(page),
        output: html,
        buildMs: performance.now() - buildStart,
        builtAt: new Date().toISOString(),
      };
      stats.pagesBuilt += 1;
    }

    this.context.pages = pages;

    this.pipeline.afterBuild(this.context);

    const indexName = 'index.html';
    const indexHash = hashContent(`${sourceHashes.join('|')}|${templateHash}`);
    const cachedIndex = manifest?.entries[indexName];

    if (
      cachedIndex &&
      cachedIndex.sourceHash === indexHash &&
      cachedIndex.templateHash === templateHash
    ) {
      this.context.outputs[indexName] = cachedIndex.output;
      const indexPath = path.join(outputDir, indexName);
      if (!fs.existsSync(indexPath)) {
        fs.writeFileSync(indexPath, cachedIndex.output);
      }
      newManifest.entries[indexName] = cachedIndex;
    } else {
      const indexHtml = this.context.outputs[indexName] ?? renderIndex(pages);
      this.context.outputs[indexName] = indexHtml;
      fs.writeFileSync(path.join(outputDir, indexName), indexHtml);
      newManifest.entries[indexName] = {
        sourceHash: indexHash,
        templateHash,
        output: indexHtml,
        buildMs: 0,
        builtAt: new Date().toISOString(),
      };
    }

    saveCache(cachePath, newManifest);

    stats.totalMs = performance.now() - started;
    return pages;
  }
}

/** Deep-clone a page so the cached copy never shares state with the build. */
function clonePage(page: Page): Page {
  return JSON.parse(JSON.stringify(page)) as Page;
}

/** Deep-clone a cached page back into a fresh object for this build. */
function restorePage(cached: Page): Page {
  return JSON.parse(JSON.stringify(cached)) as Page;
}

/** Build an engine for the given options, loading the config and plugins. */
export function createEngine(options: EngineOptions): SSGEngine {
  const loaded = loadConfig(options.config);
  const plugins = loadPlugins(loaded, options);
  const context: PluginContext = { options, pages: [], outputs: {} };
  return new SSGEngine(plugins, context, options);
}

/**
 * Build the site: load the config and plugins, run the plugin pipeline, and
 * write every page plus the site index into the output directory.
 */
export function buildSite(options: BuildOptions): Page[] {
  return createEngine(options).run();
}
