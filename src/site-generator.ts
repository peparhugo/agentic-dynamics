import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import { MarkdownPlugin, markdownFiles, setMarkdownSource } from './plugins/markdown';
import { TemplatePlugin, getRenderedHtml } from './plugins/template';
import { Plugin, PluginContext, resolveBuildOptions } from './plugin';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface BuildResult {
  pages: Page[];
  indexPath: string;
}
export { parseMarkdown } from './plugins/markdown';
export type { Plugin, PluginContext } from './plugin';

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function pageDocument(page: Page): string {
  const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
  return document(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata ? `<p>${metadata}</p>\n` : ''}${page.html}</main>`);
}

function indexDocument(pages: Page[]): string {
  const links = pages.map((page) => {
    const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildResult> {
  const resolved = resolveBuildOptions(options);
  const configuredPlugins = await loadConfiguredPlugins(resolved.configFile, resolved.plugins);
  const plugins = [new MarkdownPlugin(), ...configuredPlugins, new TemplatePlugin()];
  const context: PluginContext = { options: resolved, pages: [] };
  await runLifecycle(plugins, 'onStart', context);
  await runLifecycle(plugins, 'beforeBuild', context);
  const sourceFiles = await markdownFiles(resolved.contentDir);
  for (const sourcePath of sourceFiles) {
    const source = await fs.readFile(sourcePath, 'utf8');
    const relativePath = path.relative(resolved.contentDir, sourcePath);
    let page: Page = { sourcePath: relativePath, outputPath: relativePath.replace(/\.md$/i, '.html'), title: path.basename(relativePath, path.extname(relativePath)), tags: [], html: '' };
    setMarkdownSource(page, source);
    for (const plugin of plugins) {
      if (plugin.onFile) page = (await plugin.onFile(page, context)) ?? page;
      setMarkdownSource(page, source);
    }
    context.pages.push(page);
  }
  context.pages.sort((a, b) => a.outputPath.localeCompare(b.outputPath));
  await fs.mkdir(resolved.outputDir, { recursive: true });
  for (const page of context.pages) {
    const destination = path.join(resolved.outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, getRenderedHtml(page) ?? pageDocument(page), 'utf8');
  }
  const indexPath = path.join(resolved.outputDir, 'index.html');
  await fs.writeFile(indexPath, indexDocument(context.pages), 'utf8');
  const result = { pages: context.pages, indexPath };
  context.result = result;
  await runLifecycle(plugins, 'afterBuild', context);
  await runLifecycle(plugins, 'onEnd', context);
  return result;
}

async function runLifecycle(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
  for (const plugin of plugins) if (plugin[hook]) await plugin[hook]!(context);
}

async function loadConfiguredPlugins(configFile: string, explicit: Plugin[]): Promise<Plugin[]> {
  if (explicit.length) return explicit;
  let configPath = path.resolve(configFile);
  if (!fsSync.existsSync(configPath) && configPath.endsWith('.ts') && fsSync.existsSync(configPath.replace(/\.ts$/, '.js'))) configPath = configPath.replace(/\.ts$/, '.js');
  let loaded: Record<string, unknown>;
  try { loaded = loadConfigModule(configPath); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND') return [];
    throw error;
  }
  const value: unknown = loaded.default ?? loaded.plugins ?? loaded;
  const values = Array.isArray(value) ? value : [value];
  return values.flatMap((item) => {
    if (typeof item === 'function') return [item() as Plugin];
    if (item && typeof item === 'object' && 'plugins' in item && Array.isArray(item.plugins)) return item.plugins as Plugin[];
    return item ? [item as Plugin] : [];
  });
}

function loadConfigModule(configPath: string): Record<string, unknown> {
  if (!configPath.endsWith('.ts')) return require(configPath) as Record<string, unknown>;
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (module: NodeModule, filename: string): void => {
    // This keeps the CLI able to consume the TypeScript config it advertises.
    const typescript = require('typescript') as typeof import('typescript');
    const source = fsSync.readFileSync(filename, 'utf8');
    const output = typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2020 } });
    module._compile(output.outputText, filename);
  };
  try { return require(configPath) as Record<string, unknown>; }
  finally {
    if (previous) require.extensions['.ts'] = previous;
    else delete require.extensions['.ts'];
  }
}
