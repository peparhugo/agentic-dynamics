import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { Page, BuildOptions, Frontmatter, PluginContext, BuildStats } from './types';
import { loadPlugins } from './plugin';
import { computeHash, computeTemplateHash, CacheManager } from './cache';

function readPages(contentDir: string): Page[] {
  const absDir = path.resolve(contentDir);
  if (!fs.existsSync(absDir)) {
    throw new Error(`Content directory not found: ${absDir}`);
  }

  const entries = fs.readdirSync(absDir, { withFileTypes: true });
  const pages: Page[] = [];

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) {
      continue;
    }

    const filePath = path.join(absDir, entry.name);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = matter(raw);

    const slug = entry.name.replace(/\.md$/, '');
    const rawData = parsed.data as Record<string, unknown>;

    if (!rawData.title || typeof rawData.title !== 'string') {
      throw new Error(`Missing title in frontmatter for: ${entry.name}`);
    }

    let date: string | undefined;
    if (rawData.date instanceof Date) {
      date = rawData.date.toISOString().split('T')[0];
    } else if (typeof rawData.date === 'string') {
      date = rawData.date;
    }

    let tags: string[] | undefined;
    if (Array.isArray(rawData.tags)) {
      tags = rawData.tags.map((t) => String(t));
    }

    const frontmatter: Frontmatter = {
      title: rawData.title,
      date,
      tags,
    };

    if (rawData.template && typeof rawData.template === 'string') {
      frontmatter.template = rawData.template;
    }
    if (rawData.layout === false || rawData.layout === '') {
      frontmatter.layout = '';
    } else if (rawData.layout && typeof rawData.layout === 'string') {
      frontmatter.layout = rawData.layout;
    }

    pages.push({
      frontmatter,
      content: parsed.content,
      slug,
    });
  }

  pages.sort((a, b) => {
    if (a.frontmatter.date && b.frontmatter.date) {
      return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
    }
    if (a.frontmatter.date) return -1;
    if (b.frontmatter.date) return 1;
    return a.frontmatter.title.localeCompare(b.frontmatter.title);
  });

  return pages;
}

export function build(options: BuildOptions): BuildStats {
  const plugins = loadPlugins();

  const ctx: PluginContext = { options, pages: [] };

  for (const plugin of plugins) {
    plugin.onStart?.(ctx);
  }

  const templatesDir = path.resolve(options.templatesDir || './templates');
  const templateHash = computeTemplateHash(templatesDir);

  const contentDir = path.resolve(options.contentDir);
  const cacheFile = path.resolve(contentDir, '..', '.ssg-cache.json');
  const cacheManager = new CacheManager(cacheFile);

  const incremental = !!options.incremental;
  const clean = !!options.clean;

  if (clean) {
    cacheManager.clear();
  }

  if (incremental && !clean) {
    cacheManager.load();
  }

  for (const plugin of plugins) {
    plugin.beforeBuild?.(ctx);
  }

  const pages = readPages(options.contentDir);
  ctx.pages = pages;

  const absOutputDir = path.resolve(options.outputDir);
  fs.mkdirSync(absOutputDir, { recursive: true });

  const absContentDir = path.resolve(options.contentDir);
  let pagesBuilt = 0;
  let pagesSkipped = 0;

  for (const page of pages) {
    const filePath = path.join(absContentDir, `${page.slug}.md`);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const contentHash = computeHash(raw);

    if (incremental && !clean) {
      const cached = cacheManager.get(filePath, contentHash, templateHash);
      if (cached) {
        page.html = cached.html;
        pagesSkipped++;
        continue;
      }
    }

    for (const plugin of plugins) {
      plugin.onFile?.(page, ctx);
    }
    pagesBuilt++;

    if (incremental && !clean && page.html !== undefined) {
      cacheManager.set(filePath, contentHash, templateHash, page.html);
    }
  }

  for (const page of pages) {
    if (page.html !== undefined) {
      const outPath = path.join(absOutputDir, `${page.slug}.html`);
      fs.writeFileSync(outPath, page.html, 'utf-8');
    }
  }

  if (ctx._renderIndex) {
    const pagesData = pages.map((page) => ({
      title: page.frontmatter.title,
      slug: page.slug,
      date: page.frontmatter.date || null,
    }));
    const indexHtml = ctx._renderIndex(pagesData);
    fs.writeFileSync(path.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
  }

  for (const plugin of plugins) {
    plugin.afterBuild?.(ctx);
  }

  for (const plugin of plugins) {
    plugin.onEnd?.(ctx);
  }

  if (incremental && !clean) {
    cacheManager.updateTemplateHash(templateHash);
    cacheManager.save();
  }

  return {
    pagesBuilt,
    pagesSkipped,
    totalPages: pages.length,
  };
}
