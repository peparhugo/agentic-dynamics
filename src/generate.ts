import { promises as fs } from 'fs';
import path from 'path';
import { extractFrontmatter } from './frontmatter';
import { renderMarkdown } from './markdown';
import { createPipeline } from './plugin';
import type { Plugin, PluginContext, PluginPipeline } from './plugin';
import { createBuiltInPlugins, loadUserPlugins, resolveConfig } from './config';
import type { BuildOptions } from './config';
import { TemplatePlugin } from './plugins/template';
import type { Page } from './types';
import {
  computeTemplatesHash,
  hashString,
  loadManifest,
  MANIFEST_VERSION,
  saveManifest,
} from './cache';
import type { CacheManifest, CachedPage } from './cache';

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  stats: BuildStats;
}

export interface BuildSetup {
  context: PluginContext;
  pipeline: PluginPipeline;
  templatePlugin: TemplatePlugin;
  plugins: Plugin[];
}

interface RawPage extends Page {
  markdown: string;
}

interface BuiltPage {
  page: Page;
  rendered: string;
  sourceHash: string;
  outPath: string;
}

export async function listMarkdownFiles(dir: string): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await listMarkdownFiles(full)));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

function toTitle(slug: string): string {
  const base = path.basename(slug);
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ParsedSource {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  markdown: string;
  template?: string;
  layout?: string;
}

function parseSource(source: string, filePath: string, contentDir: string): ParsedSource {
  const { frontmatter, content } = extractFrontmatter(source);
  const rel = path.relative(contentDir, filePath).split(path.sep).join('/');
  const slug = rel.replace(/\.md$/i, '');
  const title = frontmatter.title || toTitle(slug);
  return {
    slug,
    title,
    date: frontmatter.date,
    tags: frontmatter.tags,
    markdown: content,
    template: frontmatter.template,
    layout: frontmatter.layout,
  };
}

function slugFromPath(filePath: string, contentDir: string): string {
  const rel = path.relative(contentDir, filePath).split(path.sep).join('/');
  return rel.replace(/\.md$/i, '');
}

export async function readPage(filePath: string, contentDir: string): Promise<Page> {
  const source = await fs.readFile(filePath, 'utf8');
  const parsed = parseSource(source, filePath, contentDir);
  return {
    slug: parsed.slug,
    title: parsed.title,
    date: parsed.date,
    tags: parsed.tags,
    html: renderMarkdown(parsed.markdown),
    template: parsed.template,
    layout: parsed.layout,
  };
}

async function parseRawPageFromSource(
  source: string,
  filePath: string,
  contentDir: string
): Promise<RawPage> {
  const parsed = parseSource(source, filePath, contentDir);
  return {
    slug: parsed.slug,
    title: parsed.title,
    date: parsed.date,
    tags: parsed.tags,
    html: '',
    markdown: parsed.markdown,
    template: parsed.template,
    layout: parsed.layout,
  };
}

function comparePages(a: Page, b: Page): number {
  const da = a.date ? Date.parse(a.date) : NaN;
  const db = b.date ? Date.parse(b.date) : NaN;
  const daValid = !Number.isNaN(da);
  const dbValid = !Number.isNaN(db);

  if (daValid && dbValid) {
    if (da !== db) {
      return db - da;
    }
  } else if (daValid) {
    return -1;
  } else if (dbValid) {
    return 1;
  }
  return a.title.localeCompare(b.title);
}

export async function setupBuild(
  contentDir: string,
  outputDir: string,
  templatesDir = './templates',
  options: BuildOptions = {}
): Promise<BuildSetup> {
  const config = await resolveConfig(options);
  const plugins: Plugin[] = [
    ...createBuiltInPlugins(),
    ...loadUserPlugins(config),
    ...(options.plugins ?? []),
  ];
  const context: PluginContext = {
    contentDir,
    outputDir,
    templatesDir,
    pages: [],
    config,
  };
  const pipeline = createPipeline(plugins, context);
  const templatePlugin = plugins.find((p): p is TemplatePlugin => p instanceof TemplatePlugin);
  if (!templatePlugin) {
    throw new Error('The built-in TemplatePlugin is required');
  }
  return { context, pipeline, templatePlugin, plugins };
}

async function processFile(
  filePath: string,
  source: string,
  context: PluginContext,
  pipeline: PluginPipeline,
  templatePlugin: TemplatePlugin
): Promise<BuiltPage> {
  const page = await parseRawPageFromSource(source, filePath, context.contentDir);
  await pipeline.onFile(page);
  const rendered = templatePlugin.renderPage(page);
  const outPath = path.join(context.outputDir, `${page.slug}.html`);
  return { page, rendered, sourceHash: hashString(source), outPath };
}

export async function runBuild(
  context: PluginContext,
  pipeline: PluginPipeline,
  templatePlugin: TemplatePlugin
): Promise<Page[]> {
  const files = await listMarkdownFiles(context.contentDir);
  const pages: Page[] = [];
  for (const file of files) {
    const source = await fs.readFile(file, 'utf8');
    const page = await parseRawPageFromSource(source, file, context.contentDir);
    await pipeline.onFile(page);
    pages.push(page);
  }
  pages.sort(comparePages);
  context.pages = pages;

  await fs.mkdir(context.outputDir, { recursive: true });
  await fs.writeFile(path.join(context.outputDir, 'index.html'), templatePlugin.renderIndex(pages), 'utf8');

  for (const page of pages) {
    const outPath = path.join(context.outputDir, `${page.slug}.html`);
    await fs.mkdir(path.dirname(outPath), { recursive: true });
    await fs.writeFile(outPath, templatePlugin.renderPage(page), 'utf8');
  }

  return pages;
}

async function removeFile(file: string): Promise<void> {
  try {
    await fs.unlink(file);
  } catch {
    /* ignore */
  }
}

async function fullBuildAndCache(
  context: PluginContext,
  pipeline: PluginPipeline,
  templatePlugin: TemplatePlugin,
  cacheFile: string
): Promise<{ pages: Page[]; stats: BuildStats }> {
  const templatesHash = await computeTemplatesHash(context.templatesDir);
  const files = await listMarkdownFiles(context.contentDir);

  const builtPages: BuiltPage[] = [];
  const entries: Record<string, CachedPage> = {};
  for (const file of files) {
    const source = await fs.readFile(file, 'utf8');
    const built = await processFile(file, source, context, pipeline, templatePlugin);
    builtPages.push(built);
    entries[built.page.slug] = {
      slug: built.page.slug,
      page: built.page,
      rendered: built.rendered,
      sourceHash: built.sourceHash,
      templateHash: templatesHash,
    };
  }

  const pages = builtPages.map((b) => b.page).sort(comparePages);
  context.pages = pages;

  await fs.mkdir(context.outputDir, { recursive: true });
  await fs.writeFile(path.join(context.outputDir, 'index.html'), templatePlugin.renderIndex(pages), 'utf8');
  for (const built of builtPages) {
    await fs.mkdir(path.dirname(built.outPath), { recursive: true });
    await fs.writeFile(built.outPath, built.rendered, 'utf8');
  }

  const manifest: CacheManifest = {
    version: MANIFEST_VERSION,
    templateHash: templatesHash,
    avgMsPerPage: 0,
    pages: entries,
  };
  await saveManifest(cacheFile, manifest);

  return {
    pages,
    stats: { pagesBuilt: pages.length, pagesSkipped: 0, timeSavedMs: 0 },
  };
}

async function incrementalBuild(
  context: PluginContext,
  pipeline: PluginPipeline,
  templatePlugin: TemplatePlugin,
  cacheFile: string
): Promise<{ pages: Page[]; stats: BuildStats }> {
  const templatesHash = await computeTemplatesHash(context.templatesDir);
  const manifest = await loadManifest(cacheFile);
  const files = await listMarkdownFiles(context.contentDir);

  const pages: Page[] = [];
  const entries: Record<string, CachedPage> = {};
  let pagesBuilt = 0;
  let pagesSkipped = 0;
  let builtMsTotal = 0;
  let builtCount = 0;

  for (const file of files) {
    const source = await fs.readFile(file, 'utf8');
    const sourceHash = hashString(source);
    const slug = slugFromPath(file, context.contentDir);

    const prev = manifest?.pages[slug];
    if (prev && prev.sourceHash === sourceHash && prev.templateHash === templatesHash) {
      pages.push(prev.page);
      entries[slug] = prev;
      pagesSkipped += 1;
      continue;
    }

    const pageStart = Date.now();
    const built = await processFile(file, source, context, pipeline, templatePlugin);
    builtMsTotal += Date.now() - pageStart;
    builtCount += 1;
    pages.push(built.page);
    pagesBuilt += 1;
    entries[built.page.slug] = {
      slug: built.page.slug,
      page: built.page,
      rendered: built.rendered,
      sourceHash,
      templateHash: templatesHash,
    };
  }

  pages.sort(comparePages);
  context.pages = pages;

  await fs.mkdir(context.outputDir, { recursive: true });
  await fs.writeFile(path.join(context.outputDir, 'index.html'), templatePlugin.renderIndex(pages), 'utf8');
  for (const slug of Object.keys(entries)) {
    const entry = entries[slug];
    const outPath = path.join(context.outputDir, `${slug}.html`);
    await fs.mkdir(path.dirname(outPath), { recursive: true });
    await fs.writeFile(outPath, entry.rendered, 'utf8');
  }

  const avgMs = builtCount > 0 ? builtMsTotal / builtCount : manifest?.avgMsPerPage ?? 0;
  const timeSavedMs = Math.round(pagesSkipped * avgMs);

  const next: CacheManifest = {
    version: MANIFEST_VERSION,
    templateHash: templatesHash,
    avgMsPerPage: avgMs,
    pages: entries,
  };
  await saveManifest(cacheFile, next);

  return {
    pages,
    stats: { pagesBuilt, pagesSkipped, timeSavedMs },
  };
}

export async function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = './templates',
  options: BuildOptions = {}
): Promise<BuildResult> {
  const { context, pipeline, templatePlugin } = await setupBuild(
    contentDir,
    outputDir,
    templatesDir,
    options
  );

  await pipeline.onStart();
  await pipeline.beforeBuild();

  const cacheFile = options.cacheFile ?? path.join(outputDir, '.ssg-cache.json');
  const incremental = options.incremental === true && options.clean !== true;

  if (options.clean === true) {
    await removeFile(cacheFile);
  }

  let pages: Page[];
  let stats: BuildStats;

  if (incremental) {
    const result = await incrementalBuild(context, pipeline, templatePlugin, cacheFile);
    pages = result.pages;
    stats = result.stats;
  } else {
    const result = await fullBuildAndCache(context, pipeline, templatePlugin, cacheFile);
    pages = result.pages;
    stats = result.stats;
  }

  await pipeline.afterBuild();
  await pipeline.onEnd();

  return { pages, outputDir, stats };
}
