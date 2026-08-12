import type { TemplateSet } from './templates';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  markdown: string;
  data: Record<string, unknown>;
  template?: string;
  layout?: string;
}

export interface SSGConfig {
  plugins?: string[];
}

export interface PluginContext {
  config: SSGConfig;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  templates: TemplateSet;
  output: Record<string, unknown>;
}

export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';

export const PLUGIN_HOOKS: readonly PluginHook[] = [
  'onStart',
  'beforeBuild',
  'afterBuild',
  'onFile',
  'onEnd',
];

export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void | Promise<void>;
  beforeBuild?(ctx: PluginContext): void | Promise<void>;
  afterBuild?(ctx: PluginContext): void | Promise<void>;
  onFile?(page: Page, ctx: PluginContext): void | Promise<void>;
  onEnd?(ctx: PluginContext): void | Promise<void>;
}
