import path from 'node:path';
import type { BuildOptions, Page } from './generator';

export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  cleanBuild: boolean;
  pagesToBuild: Set<string>;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export function createPluginContext(options: BuildOptions = {}): PluginContext {
  return {
    options,
    contentDir: path.resolve(options.contentDir ?? 'content'),
    outputDir: path.resolve(options.outputDir ?? 'dist'),
    templatesDir: path.resolve(options.templatesDir ?? 'templates'),
    pages: [],
    cleanBuild: true,
    pagesToBuild: new Set(),
  };
}
