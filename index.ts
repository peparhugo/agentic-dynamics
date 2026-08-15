import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import type { FSWatcher } from 'chokidar';
import type { Plugin, PluginFactory, SSGConfig, BuildContext } from './plugins/types';
import { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin, injectLiveReload } from './plugins/dev-server';

export interface Frontmatter { title?: string; date?: string; tags?: string[]; template?: string; layout?: string; [key: string]: unknown; }
export interface Page { sourcePath: string; outputPath: string; title: string; date?: string; tags: string[]; html: string; frontmatter?: Frontmatter; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; plugins?: PluginFactory[]; configFile?: string; incremental?: boolean; clean?: boolean; }
export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevServer { server: ReturnType<typeof createServer>; watcher: FSWatcher; close: () => Promise<void>; }
export interface ParsedMarkdown { data: Frontmatter; content: string; }
export interface CachePage { sourceHash: string; templateHash: string; outputPath: string; frontmatter?: Frontmatter; markdownContent?: string; markdownHtml?: string; renderedHtml?: string; buildTimeMs?: number; }
export interface BuildStats { pagesBuilt: number; pagesSkipped: number; timeSaved: number; }
export interface CacheManifest { version: 1; templateHash: string; pages: Record<string, CachePage>; }
export type { Plugin, PluginFactory, SSGConfig, BuildContext } from './plugins/types';
export { parseMarkdown, MarkdownPlugin, TemplatePlugin, DevServerPlugin, injectLiveReload };

async function loadConfig(file = 'ssg.config.ts'): Promise<SSGConfig> {
  const configPath = path.resolve(file);
  try { await fs.access(configPath); } catch { return {}; }
  // TypeScript configs are loaded by ts-jest during tests and by the compiled CLI when emitted.
  const loaded = require(configPath) as SSGConfig | PluginFactory[] | { default?: SSGConfig | PluginFactory[] };
  const value = ('default' in loaded ? loaded.default : loaded) ?? {};
  return Array.isArray(value) ? { plugins: value } : value;
}
async function pluginsFor(options: BuildOptions): Promise<Plugin[]> {
  const config = await loadConfig(options.configFile);
  const factories = options.plugins ?? config.plugins ?? [];
  // Markdown must establish pages first; user plugins can then transform them before rendering.
  return [new MarkdownPlugin(), ...factories, new TemplatePlugin()].map((plugin) => typeof plugin === 'function' ? plugin() : plugin);
}
async function runHook(plugins: Plugin[], hook: keyof Plugin, ...args: [BuildContext] | [Page, BuildContext]): Promise<void> {
  for (const plugin of plugins) { const handler = plugin[hook] as ((...values: unknown[]) => void | Promise<void>) | undefined; if (handler) await handler(...args); }
}
async function hashFiles(directory: string): Promise<string> {
  const hash = createHash('sha256');
  async function visit(current: string, relative = ''): Promise<void> {
    let entries;
    try { entries = await fs.readdir(current, { withFileTypes: true }); } catch (error: unknown) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return; throw error; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const child = path.join(relative, entry.name);
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) await visit(full, child);
      else if (/\.(hbs|ejs)$/i.test(entry.name)) { hash.update(child); hash.update(await fs.readFile(full)); }
    }
  }
  await visit(directory);
  return hash.digest('hex');
}
async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const value = JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest;
    return value?.version === 1 && value.pages ? value : undefined;
  } catch { return undefined; }
}
export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content'); const outputDir = path.resolve(options.outputDir ?? './dist'); const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const context: BuildContext = { options, contentDir, outputDir, templatesDir, pages: [], files: [], metadata: {} };
  const cachePath = path.join(outputDir, '.ssg-cache.json');
  const previous = options.incremental && !options.clean ? await readManifest(cachePath) : undefined;
  const templateHash = await hashFiles(templatesDir);
  context.metadata.cache = previous;
  context.metadata.templateHash = templateHash;
  const plugins = await pluginsFor(options);
  await runHook(plugins, 'onStart', context);
  if (!previous) await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await runHook(plugins, 'beforeBuild', context);
  const incremental = Boolean(options.incremental && previous);
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
  const currentSources = new Set(context.pages.map((page) => page.sourcePath));
  const manifest: CacheManifest = { version: 1, templateHash, pages: {} };
  for (const page of context.pages) {
    const cached = previous?.pages[page.sourcePath];
    const sourceHash = (context.metadata.sourceHashes as Record<string, string> | undefined)?.[page.sourcePath];
    const unchanged = incremental && cached && cached.sourceHash === sourceHash && cached.templateHash === templateHash && await fs.access(path.join(outputDir, page.outputPath)).then(() => true).catch(() => false);
    if (unchanged) {
      stats.pagesSkipped += 1; stats.timeSaved += cached.buildTimeMs ?? 0; manifest.pages[page.sourcePath] = cached; continue;
    }
    const started = Date.now();
    await runHook(plugins, 'onFile', page, context);
    const buildTimeMs = Date.now() - started;
    const renderedHtml = await fs.readFile(path.join(outputDir, page.outputPath), 'utf8');
    manifest.pages[page.sourcePath] = { sourceHash: sourceHash ?? '', templateHash, outputPath: page.outputPath, frontmatter: page.frontmatter, markdownContent: context.metadata.markdownContent && (context.metadata.markdownContent as Record<string, string>)[page.sourcePath], markdownHtml: page.html, renderedHtml, buildTimeMs };
    stats.pagesBuilt += 1;
  }
  if (previous) for (const sourcePath of Object.keys(previous.pages)) if (!currentSources.has(sourcePath)) await fs.rm(path.join(outputDir, previous.pages[sourcePath].outputPath), { force: true });
  context.metadata.buildStats = stats;
  await runHook(plugins, 'afterBuild', context); await runHook(plugins, 'onEnd', context);
  await fs.writeFile(cachePath, JSON.stringify(manifest, null, 2), 'utf8');
  console.log(`Build stats: ${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped, ${stats.timeSaved}ms saved`);
  return context.pages;
}
export function parseArgs(args: string[]): ServeOptions { const options: ServeOptions = {}; for (let index = 0; index < args.length; index += 1) { if (args[index] === '--incremental') options.incremental = true; else if (args[index] === '--clean') options.clean = true; else if (args[index] === '--content' || args[index] === '--output' || args[index] === '--templates') { const value = args[++index]; if (!value) throw new Error(`${args[index - 1]} requires a directory`); if (args[index - 1] === '--content') options.contentDir = value; else if (args[index - 1] === '--output') options.outputDir = value; else options.templatesDir = value; } else if (args[index] === '--port') { const value = args[++index]; if (!value) throw new Error('--port requires a number'); const port = Number(value); if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port requires a valid port'); options.port = port; } } return options; }
export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> { return new DevServerPlugin().start(options, buildSite); }
export async function main(args = process.argv.slice(2)): Promise<void> { const options = parseArgs(args.slice(1)); if (args[0] === 'build') await buildSite(options); else if (args[0] === 'serve') await startDevServer(options); else throw new Error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] | ssg serve [--port <number>]'); }
if (require.main === module) main().catch((error: unknown) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
