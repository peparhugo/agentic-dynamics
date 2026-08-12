import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';
import type { BuildContext, BuildStats, CachePage, Plugin } from './plugin';
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
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildManifest {
  version: 1;
  templateHash: string;
  pages: Record<string, CachePage>;
}

let lastBuildStats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };

export function getLastBuildStats(): BuildStats {
  return { ...lastBuildStats };
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

function hashFile(filename: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
}

function templateFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? templateFiles(filename) : [filename];
  }).sort();
}

function hashTemplates(directory: string): string {
  const hash = crypto.createHash('sha256');
  for (const filename of templateFiles(directory)) hash.update(path.relative(directory, filename)).update(hashFile(filename));
  return hash.digest('hex');
}

function readManifest(filename: string): BuildManifest | undefined {
  try {
    const manifest = JSON.parse(fs.readFileSync(filename, 'utf8')) as BuildManifest;
    return manifest.version === 1 && manifest.pages ? manifest : undefined;
  } catch {
    return undefined;
  }
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const started = Date.now();
  const resolved = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? options.templateDir ?? './templates')
  };
  const files = markdownFiles(resolved.contentDir);
  const manifestFile = path.join(resolved.outputDir, '.ssg-cache.json');
  const previous = options.incremental && !options.clean ? readManifest(manifestFile) : undefined;
  const incremental = Boolean(options.incremental && previous);
  if (!incremental) fs.rmSync(resolved.outputDir, { recursive: true, force: true });
  fs.mkdirSync(resolved.outputDir, { recursive: true });
  const cache = { incremental, templateHash: hashTemplates(resolved.templatesDir), pages: incremental ? previous!.pages : {}, stats: { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 } };
  const context: BuildContext = { options: resolved, pages: [], files, cache };
  const plugins = [new MarkdownPlugin(), ...loadPlugins(), ...(options.plugins ?? []), new TemplatePlugin()];
  for (const plugin of plugins) plugin.onStart?.(context);
  for (const plugin of plugins) plugin.beforeBuild?.(context);
  for (const filename of files) {
    let page = { title: '', tags: [], slug: '', html: '', source: filename } as Page;
    for (const plugin of plugins) page = plugin.onFile?.(page, context) ?? page;
    context.pages.push(page);
  }
  context.pages.sort((a, b) => asDate(b.date) - asDate(a.date));
  for (const plugin of plugins) plugin.afterBuild?.(context);
  for (const plugin of plugins) plugin.onEnd?.(context);
  const active = new Set(files.map((filename) => path.relative(resolved.contentDir, filename)));
  for (const filename of Object.keys(cache.pages)) if (!active.has(filename)) {
    const output = path.join(resolved.outputDir, `${filename.replace(/\.md$/i, '')}.html`);
    fs.rmSync(output, { force: true });
    delete cache.pages[filename];
  }
  fs.writeFileSync(manifestFile, JSON.stringify({ version: 1, templateHash: cache.templateHash, pages: cache.pages }, null, 2));
  lastBuildStats = { ...cache.stats, timeSaved: cache.stats.pagesSkipped ? Math.max(1, Date.now() - started) : 0 };
  return context.pages;
}

export type { BuildContext, BuildStats, CachePage, Plugin } from './plugin';
