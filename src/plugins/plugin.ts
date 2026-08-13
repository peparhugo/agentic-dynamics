import type { BuildOptions, Page } from '../generator';

export interface PluginFile extends Page {
  source: string;
  data: Record<string, unknown>;
  output?: string;
}

export interface PluginContext {
  options: Required<BuildOptions>;
  pages: Page[];
  file?: PluginFile;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginFile, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}
