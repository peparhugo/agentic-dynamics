import { Page } from './types';

export interface PluginContext {
  contentDir: string;
  outputDir?: string;
  templatesDir: string;
}

/**
 * Mutable working state for a single content file as it flows through the
 * plugin pipeline. Plugins read/write these fields in place; the engine
 * converts the final draft into a public `Page` once every plugin has run.
 */
export interface PageDraft {
  slug: string;
  filename: string;
  data: Record<string, unknown>;
  content: string;
  title: string;
  date?: string;
  tags: string[];
  template: string;
  outputPath: string;
  body: string;
  html: string;
}

export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void | Promise<void>;
  beforeBuild?(ctx: PluginContext): void;
  onFile?(page: PageDraft, ctx: PluginContext): void;
  afterBuild?(pages: Page[], ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void | Promise<void>;
}
