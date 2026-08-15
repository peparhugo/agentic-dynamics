import type { BuildOptions, Page } from './types';

/**
 * Shared, mutable state threaded through a single build. Plugins read and
 * write to this context through their lifecycle hooks.
 */
export interface PluginContext {
  options: BuildOptions;
  pages: Page[];
  outputDir: string;
}

/**
 * The lifecycle contract every SSG plugin implements. All hooks are optional
 * and synchronous; the engine invokes them in plugin order for each phase.
 */
export interface Plugin {
  name: string;

  /** Runs once at the very start of a build, before any work is done. */
  onStart?(context: PluginContext): void;

  /** Runs after pages are read and before any file is rendered or written. */
  beforeBuild?(context: PluginContext): void;

  /** Runs once after all output files have been written. */
  afterBuild?(context: PluginContext): void;

  /** Runs once per page, in order, before the page is written to disk. */
  onFile?(page: Page, context: PluginContext): void;

  /** Runs once at the very end of a build. */
  onEnd?(context: PluginContext): void;
}

export type PluginLifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

/**
 * Invoke a single phase hook across every plugin, in order.
 */
export function runHook(plugins: Plugin[], hook: PluginLifecycleHook, context: PluginContext): void {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (handler) handler.call(plugin, context);
  }
}

/**
 * Invoke the per-page `onFile` hook across every plugin, in order.
 */
export function runFileHooks(plugins: Plugin[], page: Page, context: PluginContext): void {
  for (const plugin of plugins) {
    if (plugin.onFile) plugin.onFile(page, context);
  }
}
