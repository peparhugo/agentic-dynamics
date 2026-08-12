import type { BuildOptions } from './ssg';
import type { Page } from './types';

/**
 * Plugin configuration loaded from a config file (e.g. ssg.config.ts).
 */
export interface SSGConfig {
  plugins?: Plugin[];
  [key: string]: unknown;
}

/**
 * Shared context handed to every plugin hook for a single build run.
 */
export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templateDir: string;
  pages: Page[];
  config: SSGConfig;
}

/**
 * The lifecycle a plugin participates in. Hooks are invoked in plugin order
 * through the plugin pipeline orchestrated by the SSG engine:
 *
 *   onStart -> beforeBuild -> onFile (per page) -> afterBuild -> onEnd
 */
export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): Page | void;
  afterBuild?(ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void;
}
