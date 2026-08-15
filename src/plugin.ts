import { PageData } from './page';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
}

export interface Plugin {
  name: string;
  onStart?: (context: PluginContext) => Promise<void>;
  beforeBuild?: (context: PluginContext) => Promise<void>;
  onFile?: (page: PageData, context: PluginContext) => Promise<PageData>;
  afterBuild?: (pages: PageData[], context: PluginContext) => Promise<void>;
  onEnd?: (context: PluginContext) => Promise<void>;
}

export class PluginManager {
  private plugins: Plugin[] = [];

  register(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  async runOnStart(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        await plugin.onStart(context);
      }
    }
  }

  async runBeforeBuild(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) {
        await plugin.beforeBuild(context);
      }
    }
  }

  async runOnFile(page: PageData, context: PluginContext): Promise<PageData> {
    let result = page;

    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        result = await plugin.onFile(result, context);
      }
    }

    return result;
  }

  async runAfterBuild(pages: PageData[], context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.afterBuild) {
        await plugin.afterBuild(pages, context);
      }
    }
  }

  async runOnEnd(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(context);
      }
    }
  }
}
