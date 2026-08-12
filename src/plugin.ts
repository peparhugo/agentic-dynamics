import type { Page } from './types';

export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';

export interface PluginFile extends Page {
  raw: string;
  contentDir: string;
}

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  pages: Page[];
  files: string[];
  options: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Plugin {
  name: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginFile, context: PluginContext): void | PluginFile | Promise<void | PluginFile>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export class PluginManager {
  private readonly plugins: Plugin[] = [];

  constructor(plugins: Plugin[] = []) {
    for (const plugin of plugins) {
      this.register(plugin);
    }
  }

  register(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  getPlugins(): Plugin[] {
    return [...this.plugins];
  }

  async runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        await fn.call(plugin, context);
      }
    }
  }

  async runOnFile(page: PluginFile, context: PluginContext): Promise<PluginFile> {
    let current = page;
    for (const plugin of this.plugins) {
      const fn = plugin.onFile;
      if (fn) {
        const result = await fn.call(plugin, current, context);
        if (result) {
          current = result;
        }
      }
    }
    return current;
  }
}
