import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { loadPlugins } from './config';
import { renderIndex } from './output';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildOptions, BuildStats, GeneratedPage, Plugin, PluginContext, PluginPage } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';
const CACHE_FILE = '.ssg-cache.json';
const CACHE_VERSION = 1;

interface CachedPage {
  sourceHash: string;
  templateHash: string;
  renderTime: number;
  page: Omit<PluginPage, 'sourcePath' | 'outputPath'>;
}

interface BuildManifest {
  version: number;
  pages: Record<string, CachedPage>;
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function hashTemplates(directory: string): Promise<string> {
  const files = await findFiles(directory, /\.hbs$/i).catch(() => []);
  const contents = await Promise.all(files.map(async (file) => (
    `${path.relative(directory, file)}\0${await fs.readFile(file, 'utf8')}`
  )));
  return hash(contents.join('\0'));
}

async function findFiles(directory: string, pattern: RegExp): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findFiles(entryPath, pattern);
    return pattern.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function readManifest(cachePath: string): Promise<BuildManifest | undefined> {
  try {
    const manifest = JSON.parse(await fs.readFile(cachePath, 'utf8')) as BuildManifest;
    return manifest.version === CACHE_VERSION && manifest.pages && typeof manifest.pages === 'object'
      ? manifest
      : undefined;
  } catch {
    return undefined;
  }
}

async function findMarkdownFiles(directory: string): Promise<string[]> {
  return findFiles(directory, /\.md$/i);
}

async function runHook(
  plugins: Plugin[],
  hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
  context: PluginContext,
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const started = Date.now();
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const configuredPlugins = await loadPlugins(options.configFile);
  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    ...configuredPlugins,
    ...(options.plugins ?? []),
    new TemplatePlugin(),
  ];
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0, duration: 0 };
  const context: PluginContext = { contentDir, outputDir, templatesDir, pages: [], buildStats: stats };
  const cachePath = path.join(outputDir, CACHE_FILE);
  const previousManifest = options.incremental && !options.clean
    ? await readManifest(cachePath)
    : undefined;
  const canSkipPages = Boolean(previousManifest) && configuredPlugins.length === 0
    && (options.plugins?.length ?? 0) === 0;
  const templateHash = await hashTemplates(templatesDir);
  const nextManifest: BuildManifest = { version: CACHE_VERSION, pages: {} };
  const unchanged = new Set<string>();

  await runHook(plugins, 'onStart', context);
  try {
    const files = await findMarkdownFiles(contentDir);
    context.pages = await Promise.all(files.map(async (sourcePath): Promise<PluginPage> => {
      const relativePath = path.relative(contentDir, sourcePath);
      const relativeOutput = relativePath.replace(/\.md$/i, '.html');
      const source = await fs.readFile(sourcePath, 'utf8');
      const sourceHash = hash(source);
      const cached = previousManifest?.pages[relativePath];
      if (canSkipPages && cached?.sourceHash === sourceHash && cached.templateHash === templateHash
        && await fs.stat(path.join(outputDir, relativeOutput)).then((stat) => stat.isFile()).catch(() => false)) {
        unchanged.add(relativePath);
        nextManifest.pages[relativePath] = cached;
        return {
          ...cached.page,
          sourcePath,
          outputPath: path.join(outputDir, relativeOutput),
          url: relativeOutput.split(path.sep).join('/'),
          source,
        };
      }
      return {
        title: path.basename(relativePath, path.extname(relativePath)),
        tags: [],
        sourcePath,
        outputPath: path.join(outputDir, relativeOutput),
        url: relativeOutput.split(path.sep).join('/'),
        source,
        content: '',
        html: '',
        output: '',
        frontmatter: {},
      };
    }));

    if (!options.incremental || !previousManifest || options.clean) {
      await fs.rm(outputDir, { recursive: true, force: true });
      unchanged.clear();
      nextManifest.pages = {};
    } else {
      const currentFiles = new Set(files.map((file) => path.relative(contentDir, file)));
      await Promise.all(Object.keys(previousManifest.pages).map(async (relativePath) => {
        if (!currentFiles.has(relativePath)) {
          const relativeOutput = relativePath.replace(/\.md$/i, '.html');
          await fs.rm(path.join(outputDir, relativeOutput), { force: true });
        }
      }));
    }
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.pages) {
      const relativePath = path.relative(contentDir, page.sourcePath);
      if (unchanged.has(relativePath)) {
        stats.pagesSkipped += 1;
        stats.timeSaved += previousManifest?.pages[relativePath]?.renderTime ?? 0;
        continue;
      }
      const pageStarted = Date.now();
      for (const plugin of plugins) await plugin.onFile?.(page, context);
      const renderTime = Math.max(1, Date.now() - pageStarted);
      nextManifest.pages[relativePath] = {
        sourceHash: hash(page.source),
        templateHash,
        renderTime,
        page: {
          title: page.title,
          date: page.date,
          tags: page.tags,
          url: page.url,
          source: page.source,
          content: page.content,
          html: page.html,
          output: page.output,
          frontmatter: page.frontmatter,
          template: page.template,
          layout: page.layout,
        },
      };
      stats.pagesBuilt += 1;
    }
    context.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      if (left.date !== right.date) return left.date ? -1 : 1;
      return left.title.localeCompare(right.title);
    });
    await Promise.all(context.pages.map(async (page) => {
      if (unchanged.has(path.relative(contentDir, page.sourcePath))) return;
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, page.output, 'utf8');
    }));
    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
    await runHook(plugins, 'afterBuild', context);
    await fs.writeFile(cachePath, `${JSON.stringify(nextManifest, null, 2)}\n`, 'utf8');
  } finally {
    await runHook(plugins, 'onEnd', context);
  }

  stats.duration = Date.now() - started;
  options.onStats?.(stats);

  return context.pages.map((page) => ({
    title: page.title,
    date: page.date,
    tags: page.tags,
    sourcePath: page.sourcePath,
    outputPath: page.outputPath,
    url: page.url,
  }));
}
