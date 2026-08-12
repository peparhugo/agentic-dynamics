import type { BuildOptions, Page } from './generator';

export interface PluginContext {
  options: BuildOptions;
  pages: Page[];
}

export interface Plugin {
  onStart?: (context: PluginContext) => void | Promise<void>;
  beforeBuild?: (context: PluginContext) => void | Promise<void>;
  afterBuild?: (context: PluginContext) => void | Promise<void>;
  onFile?: (page: Page, context: PluginContext) => void | Promise<void>;
  onEnd?: (context: PluginContext) => void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin) | (() => Promise<Plugin>);
