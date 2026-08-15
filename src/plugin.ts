import type { Page } from './generator';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  files: string[];
  data: Map<string, unknown>;
}

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginFactory = Plugin | (() => Plugin | Promise<Plugin>);
