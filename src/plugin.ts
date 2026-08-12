import type { BuildOptions, SitePage } from './index';

export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: SitePage[];
}

export interface Plugin {
  onStart?(context: PluginContext): void;
  beforeBuild?(context: PluginContext): void;
  afterBuild?(context: PluginContext): void;
  onFile?(page: SitePage, context: PluginContext): void;
  onEnd?(context: PluginContext): void;
}

export type PluginConfig = Plugin | (() => Plugin) | string;
