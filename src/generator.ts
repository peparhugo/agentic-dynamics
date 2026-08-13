import { promises as fs } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { MarkdownPlugin } from '../plugins/markdown.js';
import { TemplatePlugin } from '../plugins/template.js';
import type { BuildContext, Page, Plugin } from '../plugins/types.js';

export type { Page, Plugin } from '../plugins/types.js';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

export interface SsgConfig {
  plugins?: Plugin[];
}

async function loadConfig(): Promise<SsgConfig> {
  const file = path.resolve('./ssg.config.ts');
  try {
    await fs.access(file);
    const config = await import(pathToFileURL(file).href);
    return (config.default ?? config) as SsgConfig;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext): Promise<void> {
  for (const plugin of plugins) {
    if (hook === 'onStart') await plugin.onStart?.(context);
    if (hook === 'beforeBuild') await plugin.beforeBuild?.(context);
    if (hook === 'afterBuild') await plugin.afterBuild?.(context);
    if (hook === 'onEnd') await plugin.onEnd?.(context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const config = await loadConfig();
  const context: BuildContext = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './site'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    files: [],
    sourcePages: [],
    pages: [],
  };
  const plugins = [new MarkdownPlugin(), ...(config.plugins ?? []), ...(options.plugins ?? []), new TemplatePlugin()];
  await runHook(plugins, 'onStart', context);
  try {
    const entries = await fs.readdir(context.contentDir, { withFileTypes: true });
    context.files = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name)).map((entry) => entry.name);
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.sourcePages) {
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    await runHook(plugins, 'afterBuild', context);
    return context.pages;
  } finally {
    await runHook(plugins, 'onEnd', context);
  }
}
