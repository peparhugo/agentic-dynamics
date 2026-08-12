import fs from 'node:fs';
import path from 'node:path';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';
import type { BuildContext, Plugin } from './plugin';
import { loadPlugins } from './plugin';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  templateDir?: string;
  plugins?: Plugin[];
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(filename) : /\.md$/i.test(entry.name) ? [filename] : [];
  });
}

function asDate(value: unknown): number {
  const time = value instanceof Date ? value.getTime() : Date.parse(String(value ?? ''));
  return Number.isNaN(time) ? 0 : time;
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const resolved = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? options.templateDir ?? './templates')
  };
  const files = markdownFiles(resolved.contentDir);
  const context: BuildContext = { options: resolved, pages: [], files };
  const plugins = [new MarkdownPlugin(), ...loadPlugins(), ...(options.plugins ?? []), new TemplatePlugin()];
  for (const plugin of plugins) plugin.onStart?.(context);
  fs.rmSync(resolved.outputDir, { recursive: true, force: true });
  fs.mkdirSync(resolved.outputDir, { recursive: true });
  for (const plugin of plugins) plugin.beforeBuild?.(context);
  for (const filename of files) {
    let page = { title: '', tags: [], slug: '', html: '', source: filename } as Page;
    for (const plugin of plugins) page = plugin.onFile?.(page, context) ?? page;
    context.pages.push(page);
  }
  context.pages.sort((a, b) => asDate(b.date) - asDate(a.date));
  for (const plugin of plugins) plugin.afterBuild?.(context);
  for (const plugin of plugins) plugin.onEnd?.(context);
  return context.pages;
}

export type { BuildContext, Plugin } from './plugin';
