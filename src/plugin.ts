import type { Page } from './generator';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port?: number;
}

export interface PluginContext {
  options: BuildOptions;
  command: 'build' | 'serve';
  pages: Page[];
  file?: { path: string; source: string; outputPath: string };
  rebuild(): Page[];
  addCleanup(cleanup: () => Promise<void> | void): void;
}

export interface Plugin {
  onStart?(context: PluginContext): void;
  beforeBuild?(context: PluginContext): void;
  afterBuild?(context: PluginContext): void;
  onFile?(page: Page, context: PluginContext): void;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
