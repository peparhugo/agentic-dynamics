import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import type { Plugin } from './plugin';
import { loadConfiguredPlugins } from './plugin';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';

export interface PageMetadata { title: string; date?: string; tags: string[]; template?: string; layout?: string; }
export interface Page { sourcePath: string; outputPath: string; metadata: PageMetadata; html: string; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; plugins?: Plugin[]; configPath?: string; incremental?: boolean; clean?: boolean; }
export interface BuildStats { pagesBuilt: number; pagesSkipped: number; timeSavedMs: number; durationMs: number; }
export interface BuildResult { pages: Page[]; stats: BuildStats; }

const markdownExtensions = new Set(['.md', '.markdown']);
const cacheFileName = '.ssg-cache.json';

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  metadata: PageMetadata;
  html: string;
  durationMs?: number;
}

interface CacheManifest {
  version: 1;
  templateHash: string;
  pages: Record<string, CacheEntry>;
}

function hash(value: string): string { return crypto.createHash('sha256').update(value).digest('hex'); }

async function templateHash(directory: string): Promise<string> {
  const files: string[] = [];
  async function collect(current: string): Promise<void> {
    let entries;
    try { entries = await fs.readdir(current, { withFileTypes: true }); }
    catch (error: unknown) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return; throw error; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) await collect(file);
      else if (['.hbs', '.handlebars', '.ejs'].includes(path.extname(entry.name).toLowerCase())) {
        files.push(`${path.relative(directory, file)}\0${await fs.readFile(file, 'utf8')}`);
      }
    }
  }
  await collect(directory);
  return hash(files.join('\0'));
}

async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try { return JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest; }
  catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function markdownFiles(directory: string): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function indexDocument(pages: Page[], outputDir: string): string {
  const items = pages.map((page) => {
    const href = path.relative(outputDir, page.outputPath).replaceAll(path.sep, '/');
    const date = page.metadata.date ? ` <time>${page.metadata.date.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')}</time>` : '';
    const title = page.metadata.title.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
    return `      <li><a href="${href.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}">${title}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>Index</title>\n</head>\n<body>\n  <main><h1>Pages</h1><ul>${items}</ul></main>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(options)).pages;
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<BuildResult> {
  const started = Date.now();
  const resolved = { contentDir: path.resolve(options.contentDir ?? './content'), outputDir: path.resolve(options.outputDir ?? './dist'), templatesDir: path.resolve(options.templatesDir ?? './templates') };
  const cachePath = path.join(resolved.outputDir, cacheFileName);
  const templatesHash = await templateHash(resolved.templatesDir);
  const previous = options.clean ? undefined : await readManifest(cachePath);
  const useCache = Boolean(options.incremental && previous && previous.version === 1 && previous.templateHash === templatesHash);
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0, durationMs: 0 };
  const cacheEntries: Record<string, CacheEntry> = {};
  const currentKeys = new Set<string>();
  const context = { options: resolved, pages: [] as Page[] };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...loadConfiguredPlugins(options.configPath), ...(options.plugins ?? [])];
  for (const plugin of plugins) await plugin.onStart?.(context);
  try {
    for (const plugin of plugins) await plugin.beforeBuild?.(context);
    for (const sourcePath of await markdownFiles(resolved.contentDir)) {
      const relativePath = path.relative(resolved.contentDir, sourcePath);
      const cacheKey = relativePath.replaceAll(path.sep, '/');
      currentKeys.add(cacheKey);
      const source = await fs.readFile(sourcePath, 'utf8');
      const sourceHash = hash(source);
      let page: Page = { sourcePath, outputPath: path.join(resolved.outputDir, relativePath.replace(/\.(md|markdown)$/i, '.html')), metadata: { title: path.basename(sourcePath, path.extname(sourcePath)), tags: [] }, html: '' };
      const cached = useCache ? previous?.pages[cacheKey] : undefined;
      const outputExists = cached ? await fs.access(page.outputPath).then(() => true).catch(() => false) : false;
      if (cached && cached.sourceHash === sourceHash && cached.templateHash === templatesHash && outputExists) {
        page = { ...page, metadata: cached.metadata, html: cached.html };
        stats.pagesSkipped++;
        stats.timeSavedMs += cached.durationMs ?? 0;
      } else {
        const pageStarted = Date.now();
        for (const plugin of plugins) { const result = await plugin.onFile?.(page, context); if (result) page = result; }
        stats.pagesBuilt++;
        cacheEntries[cacheKey] = { sourceHash, templateHash: templatesHash, metadata: page.metadata, html: page.html, durationMs: Date.now() - pageStarted };
      }
      context.pages.push(page);
    }
    await fs.mkdir(resolved.outputDir, { recursive: true });
    for (const page of context.pages) { await fs.mkdir(path.dirname(page.outputPath), { recursive: true }); await fs.writeFile(page.outputPath, page.html, 'utf8'); }
    if (useCache && previous) {
      for (const [key] of Object.entries(previous.pages)) {
        if (!currentKeys.has(key)) {
          await fs.rm(path.join(resolved.outputDir, key.replace(/\.(md|markdown)$/i, '.html')), { force: true });
        }
      }
    }
    await fs.writeFile(path.join(resolved.outputDir, 'index.html'), indexDocument(context.pages, resolved.outputDir), 'utf8');
    for (const page of context.pages) {
      const key = path.relative(resolved.contentDir, page.sourcePath).replaceAll(path.sep, '/');
      if (!cacheEntries[key]) {
        const old = previous?.pages[key];
        cacheEntries[key] = { sourceHash: hash(await fs.readFile(page.sourcePath, 'utf8')), templateHash: templatesHash, metadata: page.metadata, html: page.html, durationMs: old?.durationMs };
      }
    }
    await fs.writeFile(cachePath, JSON.stringify({ version: 1, templateHash: templatesHash, pages: cacheEntries }, null, 2), 'utf8');
    for (const plugin of plugins) await plugin.afterBuild?.(context);
    stats.durationMs = Date.now() - started;
    return { pages: context.pages, stats };
  } finally {
    for (const plugin of plugins) await plugin.onEnd?.(context);
  }
}

export type { BuildContext, Plugin, PluginExport, SsgConfig } from './plugin';
export { loadConfiguredPlugins } from './plugin';
