import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createServer } from 'node:http';
import type { FSWatcher } from 'chokidar';
import type { Plugin, PluginFactory, SSGConfig, BuildContext } from './plugins/types';
import { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin, injectLiveReload } from './plugins/dev-server';

export interface Frontmatter { title?: string; date?: string; tags?: string[]; template?: string; layout?: string; [key: string]: unknown; }
export interface Page { sourcePath: string; outputPath: string; title: string; date?: string; tags: string[]; html: string; frontmatter?: Frontmatter; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; plugins?: PluginFactory[]; configFile?: string; }
export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevServer { server: ReturnType<typeof createServer>; watcher: FSWatcher; close: () => Promise<void>; }
export interface ParsedMarkdown { data: Frontmatter; content: string; }
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
export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content'); const outputDir = path.resolve(options.outputDir ?? './dist'); const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const context: BuildContext = { options, contentDir, outputDir, templatesDir, pages: [], files: [], metadata: {} };
  const plugins = await pluginsFor(options); await runHook(plugins, 'onStart', context); await fs.rm(outputDir, { recursive: true, force: true }); await fs.mkdir(outputDir, { recursive: true }); await runHook(plugins, 'beforeBuild', context);
  for (const page of context.pages) await runHook(plugins, 'onFile', page, context);
  await runHook(plugins, 'afterBuild', context); await runHook(plugins, 'onEnd', context); return context.pages;
}
export function parseArgs(args: string[]): ServeOptions { const options: ServeOptions = {}; for (let index = 0; index < args.length; index += 1) { if (args[index] === '--content' || args[index] === '--output' || args[index] === '--templates') { const value = args[++index]; if (!value) throw new Error(`${args[index - 1]} requires a directory`); if (args[index - 1] === '--content') options.contentDir = value; else if (args[index - 1] === '--output') options.outputDir = value; else options.templatesDir = value; } else if (args[index] === '--port') { const value = args[++index]; if (!value) throw new Error('--port requires a number'); const port = Number(value); if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port requires a valid port'); options.port = port; } } return options; }
export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> { return new DevServerPlugin().start(options, buildSite); }
export async function main(args = process.argv.slice(2)): Promise<void> { const options = parseArgs(args.slice(1)); if (args[0] === 'build') await buildSite(options); else if (args[0] === 'serve') await startDevServer(options); else throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] | ssg serve [--port <number>]'); }
if (require.main === module) main().catch((error: unknown) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
