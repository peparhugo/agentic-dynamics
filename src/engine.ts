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
 */

import fs from 'fs';
import path from 'path';

import { loadConfig, loadPlugins } from './config';
import { loadPages } from './load';
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
    const { contentDir, outputDir } = this.options;
    fs.mkdirSync(outputDir, { recursive: true });

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

    return pages;
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
