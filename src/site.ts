import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { MarkdownPlugin } from './plugins/markdown';
import type { BuildContext, Plugin } from './plugins/plugin';
import { TemplatePlugin } from './plugins/template';
import { loadConfig } from './config';

export interface Page {
  sourcePath?: string;
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

function markdownFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  });
}

function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext, page?: Page): void {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    if (hook === 'onFile' && page) (handler as (file: Page, build: BuildContext) => void)(page, context);
    else (handler as (build: BuildContext) => void)(context);
  }
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const config = loadConfig();
  const mergedOptions = { ...config, ...options, plugins: options.plugins ?? config.plugins };
  const context: BuildContext = {
    contentDir: resolve(mergedOptions.contentDir ?? 'content'),
    outputDir: resolve(mergedOptions.outputDir ?? 'dist'),
    templatesDir: resolve(mergedOptions.templatesDir ?? 'templates'),
    pages: []
  };
  if (!existsSync(context.contentDir)) throw new Error(`Content directory does not exist: ${context.contentDir}`);

  const plugins = [new MarkdownPlugin(), ...(mergedOptions.plugins ?? []), new TemplatePlugin()];
  runHook(plugins, 'onStart', context);
  try {
    rmSync(context.outputDir, { recursive: true, force: true });
    mkdirSync(context.outputDir, { recursive: true });
    runHook(plugins, 'beforeBuild', context);
    for (const sourcePath of markdownFiles(context.contentDir)) {
      const page: Page = { sourcePath, title: '', tags: [], outputPath: '', url: '', html: '' };
      runHook(plugins, 'onFile', context, page);
      context.pages.push(page);
    }
    context.pages.sort((left, right) => left.title.localeCompare(right.title));
    runHook(plugins, 'afterBuild', context);
    for (const page of context.pages) delete page.sourcePath;
    return context.pages;
  } finally {
    runHook(plugins, 'onEnd', context);
  }
}

export type { BuildContext, Plugin } from './plugins/plugin';
