import type { Page } from '../types';

/**
 * A plugin module from `./plugins/` or the `ssg.config.ts` file can either
 * export a ready-made `Plugin` instance or a factory that receives the
 * shared context and returns one.
 */
export type PluginFactory = (context: PluginContext) => Plugin;

/**
 * The configuration file (`ssg.config.ts`) shape. Directory options can be
 * overridden by command-line flags; the `plugins` array lists plugin modules
 * under `./plugins/` (by name or path) or inline plugin factories.
 */
export interface SSGConfig {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  plugins?: Array<string | Plugin | PluginFactory>;
  [key: string]: unknown;
}

/**
 * The lifecycle hooks a plugin may implement. Every hook in the pipeline is
 * invoked for each plugin in registration order.
 */
export interface Plugin {
  /** Unique name, used for diagnostics and ordering. */
  name: string;
  /** Runs once when the engine starts (before any build). */
  onStart?(context: PluginContext): void | Promise<void>;
  /** Runs before the site is built (prepare templates, directories, ...). */
  beforeBuild?(context: PluginContext): void | Promise<void>;
  /** Runs after every page has been produced (write output, ...). */
  afterBuild?(context: PluginContext): void | Promise<void>;
  /**
   * Runs for every file in the content directory. May return a page to
   * include it in the build, a modified page, or `undefined`/`null` to skip
   * the file entirely.
   */
  onFile?(page: Page, context: PluginContext): Page | undefined | null | void | Promise<Page | undefined | null | void>;
  /** Runs once when the engine finishes (cleanup, ...). */
  onEnd?(context: PluginContext): void | Promise<void>;
}

/**
 * Shared state handed to every plugin. The engine exposes the resolved
 * directories, the accumulated pages, and an `engine` reference so plugins
 * can trigger rebuilds (used by the dev-server plugin).
 */
export interface PluginContext {
  /** The command being run: `build` or `serve`. */
  command: 'build' | 'serve';
  /** The loaded configuration file (empty object when none is present). */
  config: SSGConfig;
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  /** Pages collected so far; populated by the engine. */
  pages: Page[];
  /** The plugins participating in this run, in order. */
  plugins: Plugin[];
  /** Arbitrary shared storage between plugins. */
  shared: Record<string, unknown>;
  /** The engine driving the pipeline. */
  engine: PluginEngine;
}

/** The subset of the engine plugins can drive. */
export interface PluginEngine {
  build(): Promise<Page[]>;
  buildSync(): Page[];
}
