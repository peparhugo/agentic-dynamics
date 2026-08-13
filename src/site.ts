import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import { runHook, type BuildContext, type Plugin } from './plugin.js';
import { loadPlugins } from './config.js';

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export type BuildResult = Page[] & { stats: BuildStats };

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  outputPath: string;
}

interface CacheManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

const cacheFileName = '.ssg-cache.json';

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map(async (entry) => {
      const filePath = path.join(directory, entry.name);
      return entry.isDirectory() ? filesIn(filePath) : [filePath];
    }))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function readManifest(filePath: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await fs.readFile(filePath, 'utf8')) as CacheManifest;
    return manifest.version === 1 && manifest.pages ? manifest : undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character] ?? character);
}

export function renderPage(page: Page): string {
  const details = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <main>
    <a href="/index.html">Home</a>
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${details}
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
${items}
    </ul>
  </main>
</body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildResult> {
  const context: BuildContext = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    pages: [],
    incremental: options.incremental === true,
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...(options.plugins ?? await loadPlugins())];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  const cachePath = path.join(context.outputDir, cacheFileName);
  const previousManifest = context.incremental && !options.clean ? await readManifest(cachePath) : undefined;
  const cleanBuild = !context.incremental || options.clean === true || previousManifest === undefined;
  if (cleanBuild) await fs.rm(context.outputDir, { recursive: true, force: true });
  await fs.mkdir(context.outputDir, { recursive: true });
  const templateFiles = await filesIn(context.templatesDir);
  const templateHash = hash((await Promise.all(templateFiles.map(async (filePath) => `${path.relative(context.templatesDir, filePath)}:${hash(await fs.readFile(filePath, 'utf8'))}`))).sort().join('\n'));
  const manifest: CacheManifest = { version: 1, pages: {} };
  let pagesBuilt = 0;
  let pagesSkipped = 0;
  for (const page of context.pages) {
    const sourceHash = hash(await fs.readFile(page.sourcePath, 'utf8'));
    manifest.pages[page.sourcePath] = { sourceHash, templateHash, outputPath: page.outputPath };
    const cached = previousManifest?.pages[page.sourcePath];
    const unchanged = !cleanBuild
      && cached?.sourceHash === sourceHash
      && cached?.templateHash === templateHash
      && cached?.outputPath === page.outputPath
      && await fs.access(page.outputPath).then(() => true).catch(() => false);
    if (unchanged) {
      pagesSkipped += 1;
      continue;
    }
    pagesBuilt += 1;
    await runHook(plugins, 'onFile', page, context);
  }
  if (!cleanBuild && previousManifest) {
    await Promise.all(Object.entries(previousManifest.pages)
      .filter(([sourcePath]) => !manifest.pages[sourcePath])
      .map(async ([, entry]) => fs.rm(entry.outputPath, { force: true })));
  }
  await runHook(plugins, 'afterBuild', context);
  await fs.writeFile(cachePath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  await runHook(plugins, 'onEnd', context);
  const stats: BuildStats = { pagesBuilt, pagesSkipped, timeSaved: pagesSkipped };
  return Object.assign(context.pages, { stats });
}
