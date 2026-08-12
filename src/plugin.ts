import type { BuildOptions, Page } from './types';

export interface PluginContext {
  options: BuildOptions;
  pages: Page[];
  outputs: Map<string, string>;
  shared: Map<string, unknown>;
}

export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void | Promise<void>;
  beforeBuild?(ctx: PluginContext): void | Promise<void>;
  afterBuild?(ctx: PluginContext): void | Promise<void>;
  onFile?(page: Page, ctx: PluginContext): void | Promise<void>;
  onEnd?(ctx: PluginContext): void | Promise<void>;
}

export class PluginPipeline {
  private readonly _plugins: Plugin[];

  constructor(plugins: Plugin[] = []) {
    this._plugins = [...plugins];
  }

  get plugins(): Plugin[] {
    return this._plugins;
  }

  use(plugin: Plugin): PluginPipeline {
    this._plugins.push(plugin);
    return this;
  }

  async runStart(ctx: PluginContext): Promise<void> {
    for (const plugin of this._plugins) {
      if (plugin.onStart) {
        await plugin.onStart(ctx);
      }
    }
  }

  async runBeforeBuild(ctx: PluginContext): Promise<void> {
    for (const plugin of this._plugins) {
      if (plugin.beforeBuild) {
        await plugin.beforeBuild(ctx);
      }
    }
  }

  async runOnFile(page: Page, ctx: PluginContext): Promise<void> {
    for (const plugin of this._plugins) {
      if (plugin.onFile) {
        await plugin.onFile(page, ctx);
      }
    }
  }

  async runAfterBuild(ctx: PluginContext): Promise<void> {
    for (const plugin of this._plugins) {
      if (plugin.afterBuild) {
        await plugin.afterBuild(ctx);
      }
    }
  }

  async runOnEnd(ctx: PluginContext): Promise<void> {
    for (const plugin of this._plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(ctx);
      }
    }
  }
}
