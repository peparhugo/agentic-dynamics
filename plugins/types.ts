import type { BuildOptions, Frontmatter, Page, ServeOptions } from '../index';

export interface BuildContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  files: string[];
  metadata: Record<string, unknown>;
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginFactory = Plugin | (() => Plugin);

export interface SSGConfig {
  plugins?: PluginFactory[];
}

export type { BuildOptions, Frontmatter, Page, ServeOptions };
