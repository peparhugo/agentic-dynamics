import { existsSync } from 'node:fs';
import { mkdir, rm } from 'node:fs/promises';
import { resolve } from 'node:path';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { Plugin, PluginContext, SsgConfig } from './plugin';

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export interface PageData {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
  [key: string]: unknown;
}

async function runHook(plugins: Plugin[], hook: Exclude<keyof Plugin, 'onFile'>, context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    await handler(context);
  }
}

async function runFileHook(plugins: Plugin[], page: Page, context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    if (plugin.onFile) await plugin.onFile(page, context);
  }
}

function configuredPlugins(): Plugin[] {
  const configPath = resolve('ssg.config.ts');
  if (!existsSync(configPath)) return [];
  // Register TypeScript support when the compiled CLI loads a TypeScript config.
  try { require('ts-node/register/transpile-only'); } catch { /* ts-node is already registered or unavailable. */ }
  const loaded = require(configPath) as SsgConfig | Plugin[] | { default?: SsgConfig | Plugin[] };
  const config = 'default' in loaded && loaded.default ? loaded.default : loaded;
  return Array.isArray(config) ? config : config.plugins ?? [];
}

export class SsgEngine {
  constructor(private readonly plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin()]) {}

  async build(options: BuildOptions = {}): Promise<Page[]> {
    const context: PluginContext = {
      options: {
        contentDir: resolve(options.contentDir ?? 'content'),
        outputDir: resolve(options.outputDir ?? 'dist'),
        templatesDir: resolve(options.templatesDir ?? 'templates')
      },
      pages: [],
      sourcePages: []
    };
    await runHook(this.plugins, 'onStart', context);
    await rm(context.options.outputDir, { recursive: true, force: true });
    await mkdir(context.options.outputDir, { recursive: true });
    await runHook(this.plugins, 'beforeBuild', context);
    for (const page of context.pages) await runFileHook(this.plugins, page, context);
    await runHook(this.plugins, 'afterBuild', context);
    await runHook(this.plugins, 'onEnd', context);
    return context.pages;
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return new SsgEngine([new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins()]).build(options);
}
