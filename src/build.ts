import * as fs from 'fs';
import * as path from 'path';
import { BuildOptions, Page, normalizeTags } from './ssg';
import { Plugin, PluginContext, applyOnFile, createPluginContext, runSyncHooks } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { loadConfiguredPlugins } from './load-plugins';
import {
  CachedPage,
  CACHE_FILE_NAME,
  CacheManifest,
  createEmptyManifest,
  hashDirectoryContents,
  hashString,
  loadManifest,
  parseFrontmatterCached,
  saveManifest,
} from './cache';

function slugFromFilename(filename: string): string {
  const ext = path.extname(filename);
  return filename.slice(0, filename.length - ext.length);
}

/** Recursively collect all .md file paths under a directory, sorted by path. */
export function findMarkdownFiles(contentDir: string): string[] {
  const results: string[] = [];

  function walk(dir: string): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
        results.push(full);
      }
    }
  }

  if (fs.existsSync(contentDir)) {
    walk(contentDir);
  }
  return results;
}

interface RawPageEntry {
  page: Page;
  file: string;
  raw: string;
}

function comparePages(a: Page, b: Page): number {
  const ad = a.date || '';
  const bd = b.date || '';
  if (ad === bd) {
    return a.title.localeCompare(b.title);
  }
  return ad < bd ? 1 : -1;
}

function loadRawPageEntries(contentDir: string): RawPageEntry[] {
  const files = findMarkdownFiles(contentDir);
  const entries: RawPageEntry[] = [];

  for (const file of files) {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, content } = parseFrontmatterCached(raw);
    const slug = slugFromFilename(path.basename(file));
    entries.push({
      file,
      raw,
      page: {
        slug,
        title: frontmatter.title || slug,
        date: frontmatter.date,
        tags: normalizeTags(frontmatter.tags),
        html: '',
        content,
        template: frontmatter.template,
        layout: frontmatter.layout,
        frontmatter,
      },
    });
  }

  return entries.sort((a, b) => comparePages(a.page, b.page));
}

function loadRawPages(contentDir: string): Page[] {
  return loadRawPageEntries(contentDir).map((entry) => entry.page);
}

export function loadPages(contentDir: string): Page[] {
  const markdown = new MarkdownPlugin();
  return loadRawPages(contentDir).map((page) => markdown.render(page));
}

export interface BuildStats {
  /** Number of pages whose source/template changed and were re-rendered. */
  pagesBuilt: number;
  /** Number of pages reused from the cache without re-rendering. */
  pagesSkipped: number;
  /** Estimated time saved by skipping unchanged pages, in milliseconds. */
  timeSavedMs: number;
}

export interface BuildResult {
  outputDir: string;
  writtenFiles: string[];
  stats: BuildStats;
}

export function build(options: BuildOptions): BuildResult {
  const markdown = new MarkdownPlugin();
  const template = new TemplatePlugin({ templatesDir: options.templatesDir });
  const plugins: Plugin[] = [markdown, template, ...loadConfiguredPlugins()];

  const context: PluginContext = createPluginContext(options);

  runSyncHooks(plugins, 'onStart', context);
  runSyncHooks(plugins, 'beforeBuild', context);

  const incremental = options.incremental === true;
  const clean = options.clean === true;
  const cachePath = path.join(options.outputDir, CACHE_FILE_NAME);
  const templatesDir = options.templatesDir ?? './templates';
  const templatesHash = hashDirectoryContents(templatesDir);

  const manifest: CacheManifest =
    incremental && !clean ? loadManifest(cachePath) : createEmptyManifest();

  const entries = loadRawPageEntries(options.contentDir);

  const pages: Page[] = [];
  const renderTasks: { page: Page; outputHtml?: string }[] = [];
  const nextFiles: Record<string, string> = {};
  const nextPages: Record<string, CachedPage> = {};

  let pagesBuilt = 0;
  let pagesSkipped = 0;
  const pageBuildTimes: number[] = [];
  const seenSlugs = new Set<string>();

  for (const entry of entries) {
    const sourceHash = hashString(entry.raw);
    const rel = path.relative(options.contentDir, entry.file);
    nextFiles[rel] = sourceHash;

    const cached = manifest.pages[entry.page.slug];
    const sourceUnchanged = manifest.files[rel] === sourceHash;
    const templatesUnchanged = manifest.templatesHash === templatesHash;
    const canSkip =
      incremental && !clean && cached != null && sourceUnchanged && templatesUnchanged;

    if (canSkip) {
      seenSlugs.add(entry.page.slug);
      nextPages[entry.page.slug] = cached;
      pages.push(cached.page);
      renderTasks.push({ page: cached.page });
      pagesSkipped++;
      continue;
    }

    const startedAt = Date.now();
    const page = applyOnFile(plugins, entry.page, context);
    const outputHtml = template.renderPage(page);
    pageBuildTimes.push(Date.now() - startedAt);

    seenSlugs.add(entry.page.slug);
    nextPages[entry.page.slug] = { page, outputHtml };
    pages.push(page);
    renderTasks.push({ page, outputHtml });
    pagesBuilt++;
  }

  context.pages = pages;

  fs.mkdirSync(options.outputDir, { recursive: true });

  const writtenFiles: string[] = [];

  const indexHtml = template.renderIndex(pages);
  const indexPath = path.join(options.outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf8');
  writtenFiles.push(indexPath);

  for (const task of renderTasks) {
    const pagePath = path.join(options.outputDir, `${task.page.slug}.html`);
    if (task.outputHtml !== undefined) {
      fs.writeFileSync(pagePath, task.outputHtml, 'utf8');
      writtenFiles.push(pagePath);
    } else if (!fs.existsSync(pagePath)) {
      // Cached output was missing on disk; write it back from the cache.
      fs.writeFileSync(pagePath, cachedOutputFor(task.page.slug, nextPages), 'utf8');
      writtenFiles.push(pagePath);
    }
  }

  // Remove stale output files and cache entries for deleted sources.
  for (const slug of Object.keys(manifest.pages)) {
    if (!seenSlugs.has(slug)) {
      const stalePath = path.join(options.outputDir, `${slug}.html`);
      if (fs.existsSync(stalePath)) {
        fs.unlinkSync(stalePath);
      }
    }
  }

  const timeSavedMs = pageBuildTimes.length
    ? Math.round((pageBuildTimes.reduce((sum, t) => sum + t, 0) / pageBuildTimes.length) * pagesSkipped)
    : 0;

  const stats: BuildStats = { pagesBuilt, pagesSkipped, timeSavedMs };

  saveManifest(cachePath, { version: 1, files: nextFiles, templatesHash, pages: nextPages });

  context.writtenFiles = writtenFiles;
  runSyncHooks(plugins, 'afterBuild', context);
  runSyncHooks(plugins, 'onEnd', context);

  return { outputDir: options.outputDir, writtenFiles, stats };
}

function cachedOutputFor(slug: string, pages: Record<string, CachedPage>): string {
  const cached = pages[slug];
  return cached ? cached.outputHtml : '';
}
