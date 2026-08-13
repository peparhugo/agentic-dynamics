import type { Plugin } from './plugin';
import { createPluginContext } from './plugin';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { hash, hashDirectory, type CacheManifest } from './cache';
import { MarkdownPlugin, parsePages } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { loadPlugins } from './config';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
  sourcePath: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  onBuildStats?: (stats: BuildStats) => void;
}

type Hook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

async function runHook(plugins: Plugin[], hook: Hook, context: ReturnType<typeof createPluginContext>): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function readPages(contentDir: string): Promise<Page[]> {
  return parsePages(contentDir);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context = createPluginContext(options);
  const configuredPlugins = options.plugins ?? await loadPlugins();
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins];
  await runHook(plugins, 'onStart', context);
  try {
    await runHook(plugins, 'beforeBuild', context);
    const cachePath = path.join(context.outputDir, '.ssg-cache.json');
    let previous: CacheManifest | undefined;
    if (options.incremental && !options.clean) {
      try {
        const parsed: unknown = JSON.parse(await readFile(cachePath, 'utf8'));
        if (typeof parsed === 'object' && parsed !== null && (parsed as CacheManifest).version === 1) previous = parsed as CacheManifest;
      } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
      }
    }
    const templateHash = await hashDirectory(context.templatesDir);
    const currentPages: CacheManifest['pages'] = {};
    const pageHashes = await Promise.all(context.pages.map(async (page) => [page.slug, hash(await readFile(page.sourcePath, 'utf8'))] as const));
    for (const [slug, sourceHash] of pageHashes) currentPages[slug] = { sourceHash, templateHash };
    const cleanBuild = !previous;
    context.cleanBuild = cleanBuild;
    context.pagesToBuild = new Set(context.pages.filter((page) => {
      const entry = currentPages[page.slug];
      const cached = previous?.pages[page.slug];
      return cleanBuild || cached?.sourceHash !== entry.sourceHash || cached.templateHash !== entry.templateHash;
    }).map((page) => page.slug));
    if (cleanBuild) {
      await rm(context.outputDir, { recursive: true, force: true });
      await mkdir(context.outputDir, { recursive: true });
    } else if (previous) {
      await Promise.all(Object.keys(previous.pages).filter((slug) => !currentPages[slug]).map((slug) => rm(path.join(context.outputDir, `${slug}.html`), { force: true })));
    }
    for (const page of context.pages) {
      if (context.pagesToBuild.has(page.slug)) {
        for (const plugin of plugins) await plugin.onFile?.(page, context);
      }
    }
    await runHook(plugins, 'afterBuild', context);
    await writeFile(cachePath, JSON.stringify({ version: 1, pages: currentPages } satisfies CacheManifest, null, 2));
    const stats: BuildStats = {
      pagesBuilt: context.pagesToBuild.size,
      pagesSkipped: context.pages.length - context.pagesToBuild.size,
      // Rendering time is input-dependent; this is a deterministic page-equivalent estimate.
      timeSaved: context.pages.length - context.pagesToBuild.size,
    };
    options.onBuildStats?.(stats);
    return context.pages;
  } finally {
    await runHook(plugins, 'onEnd', context);
  }
}
