import { BuildOptions, Page } from './types';

export interface PluginContext {
  options: BuildOptions;
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

export type PluginFactory = Plugin | ((context: PluginContext) => Plugin | Promise<Plugin>);
