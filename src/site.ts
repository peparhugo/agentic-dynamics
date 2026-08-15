import { readdir, readFile, rm, mkdir, access, writeFile } from 'node:fs/promises';
import { join, relative, resolve, dirname } from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import ts from 'typescript';
import type { BuildContext, BuildStats, Plugin, SsgConfig } from './plugin';
import { MarkdownPlugin, parsePage } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface Page { title: string; date?: string; tags: string[]; slug: string; html: string; template?: string; layout?: string; frontmatter: Record<string, unknown>; }
export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  onStats?: (stats: BuildStats) => void;
}
export { parsePage };

interface CacheEntry { sourceHash: string; page: Page; html: string; renderTimeMs: number; }
interface BuildCache { version: 1; templateHash: string; pages: Record<string, CacheEntry>; }

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

function clonePage(page: Page): Page {
  return JSON.parse(JSON.stringify(page)) as Page;
}

async function markdownFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map(async (entry) => entry.isDirectory() ? markdownFiles(join(directory, entry.name)) : entry.isFile() && entry.name.toLowerCase().endsWith('.md') ? [join(directory, entry.name)] : []))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function templateHash(directory: string): Promise<string> {
  async function files(path: string): Promise<string[]> {
    try {
      const entries = await readdir(path, { withFileTypes: true });
      return (await Promise.all(entries.map((entry) => entry.isDirectory() ? files(join(path, entry.name)) : entry.isFile() && entry.name.endsWith('.hbs') ? [join(path, entry.name)] : []))).flat();
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
  }
  const names = await files(directory);
  const contents = await Promise.all(names.sort().map(async (file) => `${relative(directory, file)}:${await readFile(file, 'utf8')}`));
  return hash(contents.join('\n'));
}

async function loadCache(filename: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await readFile(filename, 'utf8')) as BuildCache;
    return cache.version === 1 && typeof cache.templateHash === 'string' && cache.pages ? cache : undefined;
  } catch (error: unknown) {
    if (error instanceof SyntaxError || (error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function fileExists(filename: string): Promise<boolean> {
  try { await access(filename); return true; } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function loadConfig(filename: string): Promise<SsgConfig> {
  try {
    await access(filename);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
  const require = createRequire(filename);
  const extensions = require.extensions as Record<string, (module: NodeModule, filename: string) => void>;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, path) => {
    const source = require('node:fs').readFileSync(path, 'utf8') as string;
    (module as NodeModule & { _compile(code: string, path: string): void })._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText, path);
  };
  try {
    const loaded = require(filename) as SsgConfig | { default: SsgConfig };
    return 'default' in loaded ? loaded.default : loaded;
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: BuildContext = { contentDir: resolve(options.contentDir ?? 'content'), outputDir: resolve(options.outputDir ?? 'dist'), templateDir: resolve(options.templateDir ?? 'templates'), pages: [], stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 } };
  const config = await loadConfig(resolve(options.configFile ?? 'ssg.config.ts'));
  const plugins = [MarkdownPlugin, ...(config.plugins ?? []), ...(options.plugins ?? []), new TemplatePlugin()];
  const cacheFile = join(dirname(context.contentDir), '.ssg-cache.json');
  const cache = options.incremental && !options.clean ? await loadCache(cacheFile) : undefined;
  const currentTemplateHash = await templateHash(context.templateDir);
  const canReuse = Boolean(cache && cache.templateHash === currentTemplateHash && (config.plugins?.length ?? 0) === 0 && !options.plugins?.length);
  const nextCache: BuildCache = { version: 1, templateHash: currentTemplateHash, pages: {} };
  try {
    await runHook(plugins, 'onStart', context);
    if (!options.incremental || options.clean || !cache) await rm(context.outputDir, { recursive: true, force: true });
    await mkdir(context.outputDir, { recursive: true });
    await runHook(plugins, 'beforeBuild', context);
    for (const file of await markdownFiles(context.contentDir)) {
      context.source = await readFile(file, 'utf8');
      context.filename = relative(context.contentDir, file);
      context.page = undefined;
      context.skipRender = false;
      context.cachedHtml = undefined;
      context.cachedRenderTimeMs = undefined;
      context.renderedHtml = undefined;
      context.renderTimeMs = undefined;
      const sourceHash = hash(context.source);
      const cached = canReuse ? cache?.pages[context.filename] : undefined;
      if (cached?.sourceHash === sourceHash) {
        context.page = clonePage(cached.page);
        const output = join(context.outputDir, `${context.page.slug}.html`);
        if (await fileExists(output)) {
          context.skipRender = true;
          context.cachedRenderTimeMs = cached.renderTimeMs;
        }
        else context.cachedHtml = cached.html;
      }
      await runHook(plugins, 'onFile', context);
      if (context.page) {
        context.pages.push(context.page);
        nextCache.pages[context.filename] = { sourceHash, page: clonePage(context.page), html: context.renderedHtml ?? cached?.html ?? '', renderTimeMs: context.renderTimeMs ?? cached?.renderTimeMs ?? 0 };
      }
    }
    if (options.incremental && cache) {
      await Promise.all(Object.keys(cache.pages).filter((filename) => !nextCache.pages[filename]).map((filename) => rm(join(context.outputDir, `${filename.replace(/\.md$/i, '')}.html`), { force: true })));
    }
    await runHook(plugins, 'afterBuild', context);
    await writeFile(cacheFile, JSON.stringify(nextCache), 'utf8');
    options.onStats?.(context.stats);
    return context.pages;
  } finally { await runHook(plugins, 'onEnd', context); }
}
