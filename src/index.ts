import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import type { Plugin, PluginConfig, PluginContext } from './plugin';
import { MarkdownPlugin, pageFromMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
export { renderTemplate } from './template';
export * from './plugin';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

export interface Frontmatter { title?: string; date?: string | Date; tags?: string[] | string; [key: string]: unknown; }
export interface SitePage { title: string; date?: string; tags: string[]; source: string; output: string; template?: string; layout?: string; }
export interface BuildStats { pagesBuilt: number; pagesSkipped: number; timeSavedMs: number; durationMs: number; }
export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: PluginConfig[];
  configFile?: string;
  incremental?: boolean;
  clean?: boolean;
  onStats?: (stats: BuildStats) => void;
}

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  page: SitePage & { data?: Frontmatter; markdown?: string; rendered?: string };
  rendered: string;
  buildMs: number;
}

interface CacheManifest {
  version: 1;
  entries: Record<string, CacheEntry>;
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  const files: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...markdownFiles(file));
    else if (/\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function hashFile(file: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function templateHash(directory: string): string {
  const files: string[] = [];
  const visit = (current: string): void => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) visit(file);
      else files.push(file);
    }
  };
  visit(directory);
  const hash = crypto.createHash('sha256');
  files.sort().forEach((file) => hash.update(path.relative(directory, file)).update(fs.readFileSync(file)));
  return hash.digest('hex');
}

function readManifest(file: string): CacheManifest | undefined {
  if (!fs.existsSync(file)) return undefined;
  try {
    const manifest = JSON.parse(fs.readFileSync(file, 'utf8')) as CacheManifest;
    return manifest.version === 1 && manifest.entries ? manifest : undefined;
  } catch {
    return undefined;
  }
}

function loadPlugins(options: BuildOptions): Plugin[] {
  const configPath = path.resolve(options.configFile ?? './ssg.config.ts');
  let configured: PluginConfig[] = options.plugins ?? [];
  if (options.plugins === undefined && fs.existsSync(configPath)) {
    // Config is intentionally required at build time so it works with ts-jest and ts-node.
    const loaded = require(configPath) as { default?: PluginConfig[] | { plugins?: PluginConfig[] }; plugins?: PluginConfig[] };
    const value = loaded.default ?? loaded;
    configured = Array.isArray(value) ? value : value.plugins ?? [];
  }
  return configured.map((entry) => {
    if (typeof entry === 'string') {
      const loaded = require(path.resolve(entry));
      return (loaded.default ?? loaded) as Plugin;
    }
    return typeof entry === 'function' ? entry() : entry;
  });
}

function indexHtml(pages: SitePage[]): string {
  const escape = (value: string) => value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const items = pages.map((page) => `    <li><a href="${escape(page.output)}">${escape(page.title)}</a>${page.date ? ` <time>${escape(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html>\n<head><meta charset="utf-8"><title>Index</title></head>\n<body>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n</body>\n</html>\n`;
}

export function buildSite(options: BuildOptions = {}): SitePage[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const sourceFiles = markdownFiles(contentDir);
  const pages = sourceFiles.map((file) => pageFromMarkdown(file, contentDir));
  const manifestFile = path.join(outputDir, '.ssg-cache.json');
  const previousManifest = options.incremental && !options.clean ? readManifest(manifestFile) : undefined;
  const canIncrement = Boolean(previousManifest);
  const currentTemplateHash = templateHash(templatesDir);
  const nextEntries: Record<string, CacheEntry> = {};
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0, durationMs: 0 };
  const startTime = process.hrtime.bigint();
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages };
  const plugins = [new MarkdownPlugin(), ...loadPlugins(options), new TemplatePlugin()];
  plugins.forEach((plugin) => plugin.onStart?.(context));
  try {
    plugins.forEach((plugin) => plugin.beforeBuild?.(context));
    if (!canIncrement) fs.rmSync(outputDir, { recursive: true, force: true });
    fs.mkdirSync(outputDir, { recursive: true });
    if (previousManifest) {
      const currentSources = new Set(pages.map((page) => page.source));
      Object.entries(previousManifest.entries).forEach(([source, entry]) => {
        if (!currentSources.has(source)) {
          const staleOutput = path.resolve(outputDir, entry.page.output);
          if (staleOutput.startsWith(`${outputDir}${path.sep}`)) fs.rmSync(staleOutput, { force: true });
        }
      });
    }
    pages.forEach((page) => {
      const source = path.join(contentDir, page.source);
      const oldEntry = previousManifest?.entries[page.source];
      const destination = path.join(outputDir, page.output);
      const sourceHash = hashFile(source);
      const reusable = Boolean(oldEntry && oldEntry.sourceHash === sourceHash
        && oldEntry.templateHash === currentTemplateHash && fs.existsSync(destination));
      const pageStart = process.hrtime.bigint();
      if (reusable) {
        Object.assign(page, oldEntry.page);
        (page as SitePage & { rendered?: string }).rendered = oldEntry.rendered;
        stats.pagesSkipped += 1;
        stats.timeSavedMs += oldEntry.buildMs;
      } else {
        plugins.forEach((plugin) => plugin.onFile?.(page, context));
        const rendered = (page as SitePage & { rendered?: string }).rendered ?? '';
        fs.mkdirSync(path.dirname(destination), { recursive: true });
        fs.writeFileSync(destination, rendered);
        stats.pagesBuilt += 1;
      }
      const rendered = (page as SitePage & { rendered?: string }).rendered ?? '';
      const buildMs = Number(process.hrtime.bigint() - pageStart) / 1_000_000;
      nextEntries[page.source] = {
        sourceHash,
        templateHash: currentTemplateHash,
        page: page as CacheEntry['page'],
        rendered,
        buildMs: reusable ? oldEntry!.buildMs : buildMs,
      };
    });
    pages.sort((a, b) => a.title.localeCompare(b.title));
    fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml(pages));
    fs.writeFileSync(manifestFile, JSON.stringify({ version: 1, entries: nextEntries }, null, 2));
    plugins.forEach((plugin) => plugin.afterBuild?.(context));
  } finally {
    plugins.forEach((plugin) => plugin.onEnd?.(context));
  }
  stats.durationMs = Number(process.hrtime.bigint() - startTime) / 1_000_000;
  options.onStats?.(stats);
  return pages;
}

export { indexHtml, markdownFiles };
