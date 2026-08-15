import { Page } from './page';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  config: Record<string, unknown>;
}

/**
 * A build-pipeline extension point. Every hook is optional and synchronous:
 * the whole pipeline (and `buildSite`) is intentionally sync so the public
 * API stays a plain function call, not a Promise.
 *
 * Hook order for a single build pass: onStart, beforeBuild, onFile (once per
 * discovered content file, in file order), afterBuild, onEnd.
 */
export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): Page | void;
  afterBuild?(pages: Page[], ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void;
}
