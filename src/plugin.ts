import type { BuildOptions, Page } from './generator';

export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  files: Map<string, string | Buffer>;
  emitFile: (filePath: string, contents: string | Buffer) => void;
}

export interface Plugin {
  onStart?: (context: PluginContext) => void | Promise<void>;
  beforeBuild?: (context: PluginContext) => void | Promise<void>;
  afterBuild?: (context: PluginContext) => void | Promise<void>;
  onFile?: (page: Page, context: PluginContext) => Page | void | Promise<Page | void>;
  onEnd?: (context: PluginContext) => void | Promise<void>;
}

export type PluginConfig = Plugin | (() => Plugin | Promise<Plugin>) | string;
