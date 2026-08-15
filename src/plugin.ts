/**
 * The plugin system: a Plugin interface with lifecycle hooks and a small
 * pipeline that runs every plugin's hook in order.
 *
 * Lifecycle hooks:
 *
 *   onStart(context)        called once, before anything else happens
 *   beforeBuild(context)    called before pages are loaded/processed
 *   onFile(page, context)   called once per page as it is processed
 *   afterBuild(context)     called after every page has been processed
 *   onEnd(context)          called once the build is complete
 */

import type { BuildOptions, Page } from './types';

/** Names of the plugin lifecycle hooks, in invocation order. */
export type PluginHookName = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';

/** The lifecycle hooks in the order they are invoked during a build. */
export const PLUGIN_HOOKS: PluginHookName[] = [
  'onStart',
  'beforeBuild',
  'afterBuild',
  'onFile',
  'onEnd',
];

/**
 * Shared state passed to every plugin hook. Plugins may attach arbitrary
 * key/value data here to communicate with one another and with the engine.
 */
export interface PluginContext {
  /** The resolved build options for the current build. */
  options: BuildOptions;
  /** All pages being processed (filled in before `onFile` hooks run). */
  pages: Page[];
  /** Final HTML for each output file, keyed by file name. */
  outputs: Record<string, string>;
  [key: string]: unknown;
}

/**
 * A plugin hooks into the SSG lifecycle. Every hook is optional; hooks are
 * invoked synchronously in registration order for each lifecycle stage.
 */
export interface Plugin {
  /** Unique plugin name (used for diagnostics and ordering). */
  name: string;
  /** Runs once before any build work begins. */
  onStart?(context: PluginContext): void;
  /** Runs before pages are loaded and processed. */
  beforeBuild?(context: PluginContext): void;
  /** Runs after every page has been processed. */
  afterBuild?(context: PluginContext): void;
  /** Runs once per page, after the page has been loaded. */
  onFile?(page: Page, context: PluginContext): void;
  /** Runs once the build is complete. */
  onEnd?(context: PluginContext): void;
}

/** Invoke a single lifecycle hook across every plugin, in order. */
export function runHook(plugins: Plugin[], hook: PluginHookName, ...args: unknown[]): void {
  for (const plugin of plugins) {
    const fn = (plugin as unknown as Record<string, unknown>)[hook];
    if (typeof fn === 'function') {
      (fn as (...hookArgs: unknown[]) => void).apply(plugin, args);
    }
  }
}

/**
 * A sequential pipeline over an ordered list of plugins. Each hook method
 * runs that hook across all plugins in registration order.
 */
export class PluginPipeline {
  /** Plugins this pipeline drives, in execution order. */
  readonly plugins: Plugin[];

  constructor(plugins: Plugin[]) {
    this.plugins = plugins;
  }

  /** Run the `onStart` hook of every plugin, in order. */
  onStart(context: PluginContext): void {
    runHook(this.plugins, 'onStart', context);
  }

  /** Run the `beforeBuild` hook of every plugin, in order. */
  beforeBuild(context: PluginContext): void {
    runHook(this.plugins, 'beforeBuild', context);
  }

  /** Run the `afterBuild` hook of every plugin, in order. */
  afterBuild(context: PluginContext): void {
    runHook(this.plugins, 'afterBuild', context);
  }

  /** Run the `onFile` hook of every plugin for the given page, in order. */
  onFile(page: Page, context: PluginContext): void {
    runHook(this.plugins, 'onFile', page, context);
  }

  /** Run the `onEnd` hook of every plugin, in order. */
  onEnd(context: PluginContext): void {
    runHook(this.plugins, 'onEnd', context);
  }
}
