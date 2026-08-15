import fs from 'node:fs/promises';
import path from 'node:path';
import { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildContext, Plugin, PluginFactory } from './plugin';

export type { BuildContext, Plugin, PluginFactory } from './plugin';

export interface Frontmatter { title?: string; date?: string; tags?: string[]; [key: string]: unknown; }
export interface Page { slug: string; source: string; title: string; date?: string; tags: string[]; html: string; template?: string; layout?: string; }

async function loadConfiguredPlugins(): Promise<Plugin[]> {
  const configPath = path.resolve('ssg.config.ts');
  try { await fs.access(configPath); } catch { return []; }
  // TypeScript configs are transpiled by ts-jest in tests and by the project's build workflow.
  const loaded = await import(configPath);
  const configured = loaded.default ?? loaded.plugins ?? loaded;
  const values: PluginFactory[] = Array.isArray(configured) ? configured : configured.plugins ?? [];
  return Promise.all(values.map(async (factory) => typeof factory === 'function' ? factory() : factory));
}

export async function buildSite(contentDir = './content', outputDir = './dist', templatesDir = './templates'): Promise<Page[]> {
  const context: BuildContext = { contentDir, outputDir, templatesDir, pages: [], files: [], data: new Map() };
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(), ...(await loadConfiguredPlugins())];
  for (const plugin of plugins) await plugin.onStart?.(context);
  for (const plugin of plugins) await plugin.beforeBuild?.(context);
  for (let index = 0; index < context.pages.length; index += 1) {
    let page = context.pages[index];
    for (const plugin of plugins) { const result = await plugin.onFile?.(page, context); if (result) page = result; }
    context.pages[index] = page;
  }
  for (const plugin of plugins) await plugin.afterBuild?.(context);
  for (const plugin of plugins) await plugin.onEnd?.(context);
  return context.pages;
}

export { parseMarkdown } from './plugins/markdown';
