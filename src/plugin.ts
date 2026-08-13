import { PageData } from './generator';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  [key: string]: unknown;
}

export interface Plugin {
  name: string;
  onStart?(context: PluginContext): Promise<void> | void;
  beforeBuild?(context: PluginContext): Promise<void> | void;
  onFile?(page: PageData, context: PluginContext): Promise<void> | void;
  afterBuild?(context: PluginContext, pages: PageData[]): Promise<void> | void;
  onEnd?(context: PluginContext): Promise<void> | void;
}

export class PluginManager {
  private plugins: Plugin[] = [];

  addPlugin(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  async executeHook(
    hookName: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
    context: PluginContext,
    pages?: PageData[]
  ): Promise<void> {
    for (const plugin of this.plugins) {
      if (hookName === 'afterBuild' && pages !== undefined && plugin.afterBuild) {
        await plugin.afterBuild(context, pages);
      } else if (hookName === 'onStart' && plugin.onStart) {
        await plugin.onStart(context);
      } else if (hookName === 'beforeBuild' && plugin.beforeBuild) {
        await plugin.beforeBuild(context);
      } else if (hookName === 'onEnd' && plugin.onEnd) {
        await plugin.onEnd(context);
      }
    }
  }

  async executeFileHook(page: PageData, context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        await plugin.onFile(page, context);
      }
    }
  }

  getPlugins(): Plugin[] {
    return this.plugins;
  }

  getPlugin(name: string): Plugin | undefined {
    return this.plugins.find((plugin) => plugin.name === name);
  }
}
