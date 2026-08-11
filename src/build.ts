import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { Page, BuildOptions, Frontmatter, PluginContext } from './types';
import { loadPlugins } from './plugin';

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

export function build(options: BuildOptions): void {
  const plugins = loadPlugins();

  const ctx: PluginContext = { options, pages: [] };

  for (const plugin of plugins) {
    plugin.onStart?.(ctx);
  }

  for (const plugin of plugins) {
    plugin.beforeBuild?.(ctx);
  }

  const pages = readPages(options.contentDir);
  ctx.pages = pages;

  const absOutputDir = path.resolve(options.outputDir);
  fs.mkdirSync(absOutputDir, { recursive: true });

  for (const page of pages) {
    for (const plugin of plugins) {
      plugin.onFile?.(page, ctx);
    }
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
}
