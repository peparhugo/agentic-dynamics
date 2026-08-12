import type { Page, SiteOptions } from './generator';

export interface PluginContext {
  options: SiteOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): Page | void | Promise<Page | void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin) | { default?: Plugin | (() => Plugin); plugins?: Plugin[] };
