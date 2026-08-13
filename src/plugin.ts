import type { Page } from './types';

/** Mutable state threaded through a single build's plugin pipeline. */
export interface PluginContext {
  readonly contentDir: string;
  readonly outputDir: string;
  readonly templatesDir: string;
  readonly siteTitle: string;
  pages: Page[];
  outputFiles: string[];
}

/**
 * A build-pipeline extension. Hooks run in plugin-array order. onStart/beforeBuild fire once per
 * build; onFile fires once per page (after beforeBuild has populated ctx.pages, before afterBuild
 * writes any output); afterBuild/onEnd fire once per build after every page has been processed.
 */
export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): void;
  afterBuild?(ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void;
}
