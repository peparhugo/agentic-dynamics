import type { Page } from './types';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  config: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';

export interface PluginPipeline {
  onStart(): Promise<void>;
  beforeBuild(): Promise<void>;
  afterBuild(): Promise<void>;
  onFile(page: Page): Promise<void>;
  onEnd(): Promise<void>;
}

export function createPipeline(plugins: Plugin[], context: PluginContext): PluginPipeline {
  async function runLifecycle(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'): Promise<void> {
    for (const plugin of plugins) {
      const fn = plugin[hook];
      if (fn) {
        await fn.call(plugin, context);
      }
    }
  }

  async function runFile(page: Page): Promise<void> {
    for (const plugin of plugins) {
      if (plugin.onFile) {
        await plugin.onFile.call(plugin, page, context);
      }
    }
  }

  return {
    onStart: () => runLifecycle('onStart'),
    beforeBuild: () => runLifecycle('beforeBuild'),
    afterBuild: () => runLifecycle('afterBuild'),
    onEnd: () => runLifecycle('onEnd'),
    onFile: (page) => runFile(page),
  };
}
