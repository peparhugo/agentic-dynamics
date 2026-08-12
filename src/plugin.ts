import type { Page, BuildOptions } from './index';

export interface BuildContext {
  options: Required<BuildOptions>;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  files: string[];
  pages: Page[];
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin) | { default: Plugin | (() => Plugin) };
