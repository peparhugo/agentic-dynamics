import { Page } from './generator';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templateDir: string;
  pages: Page[];
  sources: Map<string, string>;
  renderedPages: Map<string, string>;
  parsedPages: Map<string, Page>;
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
