import { Plugin, PluginContext, FileContext } from './plugin.js';
import { PageMetadata } from './types.js';

export class PluginManager {
  private plugins: Plugin[] = [];

  constructor(plugins: Plugin[]) {
    this.plugins = plugins;
  }

  async onStart(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        await plugin.onStart(context);
      }
    }
  }

  async beforeBuild(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) {
        await plugin.beforeBuild(context);
      }
    }
  }

  async onFile(context: PluginContext, file: FileContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        await plugin.onFile(context, file);
      }
    }
  }

  async afterBuild(context: PluginContext, pages: PageMetadata[]): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.afterBuild) {
        await plugin.afterBuild(context, pages);
      }
    }
  }

  async onEnd(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(context);
      }
    }
  }

  getPlugins(): Plugin[] {
    return this.plugins;
  }

  addPlugin(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  removePlugin(pluginName: string): void {
    this.plugins = this.plugins.filter((p) => p.name !== pluginName);
  }

  getPlugin(pluginName: string): Plugin | undefined {
    return this.plugins.find((p) => p.name === pluginName);
  }
}
