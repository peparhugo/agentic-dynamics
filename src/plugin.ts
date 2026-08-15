import type { Page } from './types';

/** Arbitrary settings a plugin author can read off `PluginContext.config`. */
export interface PluginConfig {
  [key: string]: unknown;
}

/** Shared, read-only build context passed to every lifecycle hook. */
export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  config: PluginConfig;
  /**
   * Present only when the engine ran with `incremental: true`. Lets plugins
   * skip expensive re-work for pages the engine has already determined are
   * unchanged (same source content and templates) since the last cached
   * build; `onFile` is not called for these pages at all, so any skip a
   * plugin performs here is an optional, additional optimization (e.g.
   * avoiding a redundant disk write of already-correct output).
   */
  incremental?: {
    /** Source paths (relative to contentDir) of pages reused from the cache this build. */
    unchangedSourcePaths: Set<string>;
  };
}

/**
 * A plugin participates in the build by implementing any subset of these
 * lifecycle hooks. The core engine runs every plugin's implementation of a
 * given hook, in plugin registration order, before moving on to the next
 * hook in the pipeline:
 *
 *   onStart -> beforeBuild -> onFile (per discovered page) -> afterBuild -> onEnd
 *
 * Hooks are synchronous so a single build() call can stay synchronous end to
 * end, matching this SSG's existing (pre-plugin) API.
 */
export interface Plugin {
  name: string;
  /** Runs once, before the content directory is even validated. */
  onStart?(ctx: PluginContext): void;
  /** Runs once per build, after validation and before any file is processed. */
  beforeBuild?(ctx: PluginContext): void;
  /**
   * Runs once per discovered page, threading the page through every plugin
   * in order. Return an updated page to replace it for the remaining
   * plugins; returning nothing leaves the page as-is.
   */
  onFile?(page: Page, ctx: PluginContext): Page | void;
  /** Runs once per build, after every page has been processed. */
  afterBuild?(pages: Page[], ctx: PluginContext): void;
  /** Runs once per build, after afterBuild. */
  onEnd?(ctx: PluginContext): void;
}
