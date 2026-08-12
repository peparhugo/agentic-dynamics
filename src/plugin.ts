import type { SiteConfig } from './template';
import type { Page } from './types';

export interface SsgContext {
  contentDir: string;
  outputDir: string;
  siteConfig: SiteConfig;
  pages: Page[];
  options: Record<string, unknown>;
}

export interface Plugin {
  readonly name: string;
  onStart?(context: SsgContext): void | Promise<void>;
  beforeBuild?(context: SsgContext): void | Promise<void>;
  afterBuild?(context: SsgContext): void | Promise<void>;
  onFile?(page: Page, context: SsgContext): void | Promise<void>;
  onEnd?(context: SsgContext): void | Promise<void>;
}

export type PluginHookName =
  | 'onStart'
  | 'beforeBuild'
  | 'afterBuild'
  | 'onFile'
  | 'onEnd';

export class PluginPipeline {
  private readonly plugins: Plugin[];

  constructor(plugins: Plugin[]) {
    this.plugins = plugins;
  }

  getPlugins(): Plugin[] {
    return this.plugins;
  }

  get length(): number {
    return this.plugins.length;
  }

  async onStart(context: SsgContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onStart) await plugin.onStart(context);
    }
  }

  async beforeBuild(context: SsgContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) await plugin.beforeBuild(context);
    }
  }

  async afterBuild(context: SsgContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.afterBuild) await plugin.afterBuild(context);
    }
  }

  async onFile(page: Page, context: SsgContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onFile) await plugin.onFile(page, context);
    }
  }

  async onEnd(context: SsgContext): Promise<void> {
    for (const plugin of this.plugins) {
      if (plugin.onEnd) await plugin.onEnd(context);
    }
  }
}
