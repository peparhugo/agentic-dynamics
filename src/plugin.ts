import { BuildOptions, Page } from './types';

/**
 * Shared state threaded through a build's plugin pipeline. `pages` starts
 * empty and is populated during `beforeBuild` (typically by a
 * content-loading plugin such as MarkdownPlugin) before any `onFile` hook
 * runs.
 */
export interface PluginContext {
  readonly options: BuildOptions;
  pages: Page[];
}

/**
 * A build-lifecycle extension. Every hook is optional; a plugin implements
 * only the stages it cares about. Hooks run in plugin-list order within
 * each stage (see SSGEngine), so a plugin that transforms page content in
 * `onFile` must be listed before a plugin that persists it (e.g.
 * TemplatePlugin) for the transform to take effect.
 */
export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void | Promise<void>;
  beforeBuild?(ctx: PluginContext): void | Promise<void>;
  onFile?(page: Page, ctx: PluginContext): Page | void | Promise<Page | void>;
  afterBuild?(ctx: PluginContext): void | Promise<void>;
  onEnd?(ctx: PluginContext): void | Promise<void>;
}
