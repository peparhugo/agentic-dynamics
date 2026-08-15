import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdownFile } from './frontmatter';
import { renderMarkdown } from './markdown';
import { Page } from './page';
import { DEFAULT_LAYOUT_NAME, DEFAULT_TEMPLATE_NAME, INDEX_TEMPLATE_NAME, TemplateEngine } from './templates';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

function findMarkdownFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    throw new Error(`Content directory not found: ${dir}`);
  }

  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      results.push(fullPath);
    }
  }

  return results.sort();
}

function slugFromPath(contentDir: string, filePath: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExt = relative.replace(/\.md$/i, '');
  return withoutExt.split(path.sep).join('/');
}

function titleFromSlug(slug: string): string {
  const base = slug.split('/').pop() || slug;
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function buildPage(contentDir: string, filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = parseMarkdownFile(raw);
  const slug = slugFromPath(contentDir, filePath);
  const html = renderMarkdown(content);

  const title = typeof data.title === 'string' && data.title.trim() ? data.title : titleFromSlug(slug);
  const date = typeof data.date === 'string' && data.date.trim() ? data.date : null;
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
  const template = typeof data.template === 'string' && data.template.trim() ? data.template : DEFAULT_TEMPLATE_NAME;
  const layout = typeof data.layout === 'string' && data.layout.trim() ? data.layout : DEFAULT_LAYOUT_NAME;

  return {
    slug,
    title,
    date,
    tags,
    html,
    sourcePath: filePath,
    outputPath: `${slug}.html`,
    template,
    layout,
  };
}

export function buildSite(options: BuildOptions): BuildResult {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir ?? './templates');

  const files = findMarkdownFiles(contentDir);
  const pages = files.map((file) => buildPage(contentDir, file));

  const templateEngine = new TemplateEngine(templatesDir);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const destPath = path.join(outputDir, page.outputPath);
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    const html = templateEngine.render(page.template, page.layout, { ...page });
    fs.writeFileSync(destPath, html, 'utf-8');
  }

  const indexPath = path.join(outputDir, 'index.html');
  const indexHtml = templateEngine.render(INDEX_TEMPLATE_NAME, DEFAULT_LAYOUT_NAME, { title: 'Index', pages });
  fs.writeFileSync(indexPath, indexHtml, 'utf-8');

  return { pages, outputDir };
}
