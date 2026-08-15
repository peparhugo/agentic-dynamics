import * as fs from 'fs';
import * as path from 'path';
import { parseFrontmatter } from './frontmatter';
import { renderMarkdown, renderIndexBodyHtml } from './render';
import { TemplateEngine } from './templates';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  /** Directory containing layouts/ and partials/ subdirectories. Defaults to ./templates relative to the current working directory. */
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

const INDEX_LAYOUT_NAME = 'index';

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.resolve(process.cwd(), 'templates');

  if (!fs.existsSync(contentDir) || !fs.statSync(contentDir).isDirectory()) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const engine = new TemplateEngine(templatesDir);

  const markdownFiles = findMarkdownFiles(contentDir);
  const pages = markdownFiles.map((filePath) => buildPage(filePath, contentDir));
  pages.sort(comparePages);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const outPath = path.join(outputDir, page.outputFile);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    const html = engine.render(page.layout, {
      title: page.title,
      date: page.date,
      tags: page.tags,
      body: page.html,
    });
    fs.writeFileSync(outPath, html, 'utf8');
  }

  const indexLayout = engine.hasLayout(INDEX_LAYOUT_NAME) ? INDEX_LAYOUT_NAME : undefined;
  const indexHtml = engine.render(indexLayout, {
    title: 'All Pages',
    tags: [],
    body: renderIndexBodyHtml(pages),
  });
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf8');

  return { pages, outputDir };
}

function comparePages(a: Page, b: Page): number {
  if (a.date && b.date) return b.date.localeCompare(a.date);
  if (a.date) return -1;
  if (b.date) return 1;
  return a.title.localeCompare(b.title);
}

function findMarkdownFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }

  return files;
}

function buildPage(filePath: string, contentDir: string): Page {
  const raw = fs.readFileSync(filePath, 'utf8');
  const { data, content } = parseFrontmatter(raw);
  const html = renderMarkdown(content);

  const relativePath = path.relative(contentDir, filePath);
  const slug = slugify(relativePath);
  const title = typeof data.title === 'string' && data.title.trim() ? data.title : slug;
  const date = typeof data.date === 'string' && data.date.trim() ? data.date : undefined;
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
  const layout = typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined;

  return {
    slug,
    title,
    date,
    tags,
    html,
    sourcePath: relativePath,
    outputFile: `${slug}.html`,
    layout,
  };
}

function slugify(relativePath: string): string {
  const withoutExt = relativePath.replace(/\.md$/i, '');
  const slug = withoutExt
    .split(path.sep)
    .join('-')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  // "index" is reserved for the generated listing page.
  if (!slug || slug === 'index') return slug === 'index' ? 'index-page' : 'page';
  return slug;
}
