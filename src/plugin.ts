import { BuildOptions, Page } from './types';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  [key: string]: unknown;
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): Page | void | Promise<Page | void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export function createContext(options: BuildOptions): PluginContext {
  return {
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir ?? './templates',
    pages: [],
  };
}

export class PluginPipeline {
  private readonly plugins: Plugin[];

  constructor(plugins: Plugin[]) {
    this.plugins = [...plugins];
  }

  getPlugins(): Plugin[] {
    return [...this.plugins];
  }

  runOnStart(context: PluginContext): void {
    for (const plugin of this.plugins) {
      plugin.onStart?.(context);
    }
  }

  runBeforeBuild(context: PluginContext): void {
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(context);
    }
  }

  runOnFile(page: Page, context: PluginContext): Page {
    let current = page;
    for (const plugin of this.plugins) {
      const result = plugin.onFile?.(current, context);
      if (result !== undefined) {
        current = result as Page;
      }
    }
    return current;
  }

  runAfterBuild(context: PluginContext): void {
    for (const plugin of this.plugins) {
      plugin.afterBuild?.(context);
    }
  }

  runOnEnd(context: PluginContext): void {
    for (const plugin of this.plugins) {
      plugin.onEnd?.(context);
    }
  }

  async runOnStartAsync(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.onStart?.(context);
    }
  }

  async runBeforeBuildAsync(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.beforeBuild?.(context);
    }
  }

  async runOnFileAsync(page: Page, context: PluginContext): Promise<Page> {
    let current = page;
    for (const plugin of this.plugins) {
      const result = await plugin.onFile?.(current, context);
      if (result !== undefined) current = result;
    }
    return current;
  }

  async runAfterBuildAsync(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.afterBuild?.(context);
    }
  }

  async runOnEndAsync(context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.onEnd?.(context);
    }
  }
}
