import { access, mkdir, rm } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildContext, Plugin } from './plugin.js';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configPath?: string;
  plugins?: Plugin[];
}

export interface ResolvedBuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

async function configuredPlugins(configPath: string): Promise<Plugin[]> {
  const path = resolve(configPath);
  try { await access(path); } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const config = await import(pathToFileURL(path).href) as { default?: SsgConfig; plugins?: Plugin[] };
  return config.default?.plugins ?? config.plugins ?? [];
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, ...args: unknown[]): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook] as ((...hookArgs: unknown[]) => void | Promise<void>) | undefined;
    if (handler) await handler.apply(plugin, args);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const resolved: ResolvedBuildOptions = {
    contentDir: options.contentDir ?? './content',
    outputDir: options.outputDir ?? './dist',
    templatesDir: options.templatesDir ?? './templates',
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...await configuredPlugins(options.configPath ?? './ssg.config.ts'), ...(options.plugins ?? [])];
  const context: BuildContext = { options: resolved, pages: [] };

  await runHook(plugins, 'onStart', context);
  await rm(resolved.outputDir, { recursive: true, force: true });
  await mkdir(resolved.outputDir, { recursive: true });
  await runHook(plugins, 'beforeBuild', context);
  for (const page of context.pages) await runHook(plugins, 'onFile', page, context);
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return context.pages;
}
