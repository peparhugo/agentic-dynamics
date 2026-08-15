import { mkdir, readdir, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { relative, dirname, extname, join, resolve, sep } from 'node:path';
import { MarkdownPlugin, TemplatePlugin } from './builtin-plugins';
import { loadConfiguredPlugins, runHook } from './plugins';
import { renderIndex } from './render';
import { BuildContext, BuildOptions, BuildPage, BuildResult, BuildStats, Page, Plugin } from './types';

const CACHE_FILE = '.ssg-cache.json';

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  page: BuildPage;
  buildTimeMs: number;
}

interface CacheManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(path) : Promise.resolve(/\.md$/i.test(entry.name) ? [path] : []);
  }));
  return files.flat();
}

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? filesIn(path) : Promise.resolve(entry.isFile() ? [path] : []);
    }));
    return files.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function templateHash(directory: string): Promise<string> {
  const root = resolve(directory);
  const files = await filesIn(root);
  const contents = await Promise.all(files.sort().map(async (file) => `${relative(root, file)}\0${await readFile(file, 'utf8')}`));
  return hash(contents.join('\0'));
}

async function readManifest(path: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await readFile(path, 'utf8')) as CacheManifest;
    return manifest.version === 1 && manifest.pages ? manifest : undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

/** Builds a site and returns both the generated pages and incremental build statistics. */
export async function buildSiteWithStats(contentDirectory = './content', outputDirectory = './dist', templatesDirectory = './templates', plugins?: Plugin[], options: BuildOptions = {}): Promise<BuildResult> {
  const incremental = options.incremental === true && options.clean !== true;
  const contentRoot = resolve(contentDirectory);
  const outputRoot = resolve(outputDirectory);
  const manifestPath = join(outputRoot, CACHE_FILE);
  const cachedManifest = incremental ? await readManifest(manifestPath) : undefined;
  const cache = cachedManifest ?? { version: 1 as const, pages: {} };
  const currentTemplateHash = await templateHash(templatesDirectory);
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  const nextPages: Record<string, CacheEntry> = {};
  const removedPaths = new Set(Object.values(cache.pages).map((entry) => entry.page.outputPath));
  const cleanBuild = !incremental || !cachedManifest;
  if (cleanBuild) await rm(outputRoot, { recursive: true, force: true });
  await mkdir(outputRoot, { recursive: true });

  const configuredPlugins = plugins ?? loadConfiguredPlugins();
  const pipeline = configuredPlugins.length ? configuredPlugins : [MarkdownPlugin, TemplatePlugin];
  const context: BuildContext = { contentDirectory: contentRoot, outputDirectory: outputRoot, templatesDirectory: resolve(templatesDirectory), pages: [] };

  await runHook(context, pipeline, 'onStart');
  try {
    await runHook(context, pipeline, 'beforeBuild');
    const sourceFiles = await markdownFiles(contentRoot);
    for (const sourceFile of sourceFiles) {
      const relativePath = relative(contentRoot, sourceFile);
      const outputPath = relativePath.slice(0, -extname(relativePath).length).split(sep).join('/') + '.html';
      const source = await readFile(sourceFile, 'utf8');
      const sourceHash = hash(source);
      const previous = cache.pages[relativePath];
      if (incremental && previous?.sourceHash === sourceHash && previous.templateHash === currentTemplateHash) {
        const page = { ...previous.page, metadata: { ...previous.page.metadata, tags: [...previous.page.metadata.tags] } };
        context.pages.push(page);
        nextPages[relativePath] = previous;
        removedPaths.delete(outputPath);
        stats.pagesSkipped++;
        stats.timeSavedMs += previous.buildTimeMs;
        const destination = join(outputRoot, outputPath);
        await mkdir(dirname(destination), { recursive: true });
        await writeFile(destination, page.renderedHtml ?? page.html, 'utf8');
        continue;
      }
      const pageStartedAt = Date.now();
      const page: BuildPage = {
        sourceFile,
        source,
        metadata: { title: '', tags: [] },
        html: '',
        outputPath,
      };
      for (const plugin of pipeline) await plugin.onFile?.(page, context);
      context.pages.push(page);
      nextPages[relativePath] = { sourceHash, templateHash: currentTemplateHash, page, buildTimeMs: Date.now() - pageStartedAt };
      removedPaths.delete(outputPath);
      stats.pagesBuilt++;
    }

    context.pages.sort((left, right) => (right.metadata.date ?? '').localeCompare(left.metadata.date ?? '') || left.metadata.title.localeCompare(right.metadata.title));
    if (!cleanBuild) await Promise.all([...removedPaths].map(async (outputPath) => {
      try { await unlink(join(outputRoot, outputPath)); } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      }
    }));
    await Promise.all(context.pages.map(async (page) => {
      const destination = join(outputRoot, page.outputPath);
      await mkdir(dirname(destination), { recursive: true });
      await writeFile(destination, page.renderedHtml ?? page.html, 'utf8');
    }));
    await writeFile(join(outputRoot, 'index.html'), renderIndex(context.pages), 'utf8');
    await writeFile(manifestPath, JSON.stringify({ version: 1, pages: nextPages }), 'utf8');
    await runHook(context, pipeline, 'afterBuild');
    stats.timeSavedMs = Math.round(stats.timeSavedMs);
    return { pages: context.pages, stats };
  } finally {
    await runHook(context, pipeline, 'onEnd');
  }
}

/** Backwards-compatible build API returning only pages. */
export async function buildSite(contentDirectory = './content', outputDirectory = './dist', templatesDirectory = './templates', plugins?: Plugin[], options?: BuildOptions): Promise<Page[]> {
  return (await buildSiteWithStats(contentDirectory, outputDirectory, templatesDirectory, plugins, options)).pages;
}
