import { BuildOptions, Page } from './types';

export type HookResult = void | Promise<void>;

export type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

export interface Plugin {
  name: string;
  onStart?(): HookResult;
  beforeBuild?(): HookResult;
  afterBuild?(): HookResult;
  onFile?(page: Page): HookResult;
  onEnd?(): HookResult;
}

export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
}

/**
 * Runs each lifecycle hook across all plugins in registration order.
 */
export class PluginPipeline {
  constructor(readonly plugins: Plugin[]) {}

  runSync(hook: LifecycleHook): void {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        void fn.call(plugin);
      }
    }
  }

  runFileSync(page: Page): void {
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        void plugin.onFile(page);
      }
    }
  }

  async run(hook: LifecycleHook): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        await fn.call(plugin);
      }
    }
  }

  async runFile(page: Page): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        await plugin.onFile(page);
      }
    }
  }
}
