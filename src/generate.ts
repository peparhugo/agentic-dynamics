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

export interface BuildResult {
  pages: Page[];
  outputDir: string;
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

async function parseRawPage(filePath: string, contentDir: string): Promise<RawPage> {
  const source = await fs.readFile(filePath, 'utf8');
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

export async function runBuild(
  context: PluginContext,
  pipeline: PluginPipeline,
  templatePlugin: TemplatePlugin
): Promise<Page[]> {
  const files = await listMarkdownFiles(context.contentDir);
  const pages: Page[] = [];
  for (const file of files) {
    const page = await parseRawPage(file, context.contentDir);
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
  const pages = await runBuild(context, pipeline, templatePlugin);
  await pipeline.afterBuild();
  await pipeline.onEnd();

  return { pages, outputDir };
}
