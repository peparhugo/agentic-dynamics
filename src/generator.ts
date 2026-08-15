import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { Plugin, PluginContext, SsgConfig } from './plugin';
import { MarkdownPlugin, parsePage as parseMarkdownPage } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface Page { sourcePath: string; outputPath: string; slug: string; title: string; date?: string; tags: string[]; html: string; template?: string; layout?: string; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templateDir?: string; plugins?: Plugin[]; configFile?: string; }
type Frontmatter = Record<string, string | string[]>;

function parseYamlValue(value: string): string | string[] { const trimmed = value.trim(); return trimmed.startsWith('[') && trimmed.endsWith(']') ? trimmed.slice(1, -1).split(',').map((item) => item.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean) : trimmed.replace(/^['"]|['"]$/g, ''); }
export function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { data: {}, content: source };
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) { const separator = line.indexOf(':'); if (separator > 0) { const key = line.slice(0, separator).trim(); if (key) data[key] = parseYamlValue(line.slice(separator + 1)); } }
  return { data, content: source.slice(match[0].length) };
}
export const parsePage = parseMarkdownPage;

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => { const path = join(directory, entry.name); return entry.isDirectory() ? markdownFiles(path) : entry.isFile() && /\.md$/i.test(entry.name) ? Promise.resolve([path]) : Promise.resolve([]); }))).flat();
}

function loadConfig(configFile?: string): Plugin[] {
  const path = resolve(configFile ?? 'ssg.config.ts');
  try {
    // Node cannot execute TypeScript configuration files without this loader.
    if (path.endsWith('.ts') && !require.extensions['.ts']) {
      require.extensions['.ts'] = (module: NodeModule, filename: string) => {
        const typescript = require('typescript') as typeof import('typescript');
        const source = require('node:fs').readFileSync(filename, 'utf8') as string;
        (module as NodeModule & { _compile(source: string, filename: string): void })._compile(typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022, esModuleInterop: true } }).outputText, filename);
      };
    }
    const config = require(path) as SsgConfig | { default?: SsgConfig };
    return (('default' in config ? config.default : config)?.plugins) ?? [];
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND' && (error as NodeJS.ErrnoException).message.includes(path)) return [];
    throw error;
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: PluginContext, page?: Page): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    if (hook === 'onFile' && page) await (handler as NonNullable<Plugin['onFile']>)(page, context);
    else await (handler as (context: PluginContext) => void | Promise<void>)(context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: PluginContext = { contentDir: resolve(options.contentDir ?? 'content'), outputDir: resolve(options.outputDir ?? 'dist'), templateDir: resolve(options.templateDir ?? 'templates'), pages: [], sources: new Map(), renderedPages: new Map() };
  const plugins = [MarkdownPlugin, ...loadConfig(options.configFile), ...(options.plugins ?? []), TemplatePlugin];
  await runHook(plugins, 'onStart', context);
  try {
    await runHook(plugins, 'beforeBuild', context);
    const files = await markdownFiles(context.contentDir);
    context.pages = await Promise.all(files.map(async (sourcePath) => { context.sources.set(sourcePath, await readFile(sourcePath, 'utf8')); return { sourcePath, outputPath: '', slug: '', title: '', tags: [], html: '' }; }));
    for (const page of context.pages) await runHook(plugins, 'onFile', context, page);
    context.pages.sort((a, b) => a.title.localeCompare(b.title));
    await rm(context.outputDir, { recursive: true, force: true });
    await mkdir(context.outputDir, { recursive: true });
    await Promise.all(context.pages.map(async (page) => { await mkdir(dirname(page.outputPath), { recursive: true }); await writeFile(page.outputPath, context.renderedPages.get(page.outputPath) ?? page.html, 'utf8'); }));
    await runHook(plugins, 'afterBuild', context);
    return context.pages;
  } finally { await runHook(plugins, 'onEnd', context); }
}
