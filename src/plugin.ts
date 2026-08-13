import type { BuildOptions, Page, PageData } from './generator';

export interface PluginContext {
  options: Required<BuildOptions>;
  pages: Page[];
  sourcePages: Array<{ page: Page; data: PageData }>;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
