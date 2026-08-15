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
