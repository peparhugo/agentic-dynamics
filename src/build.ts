import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdown } from './markdown';
import { renderIndexHtml, renderPageHtml, DEFAULT_STYLESHEET } from './templates';
import { BuildOptions, BuildResult, Page } from './types';

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

function toSlug(contentDir: string, filePath: string): string {
  const relative = path.relative(contentDir, filePath).replace(/\.md$/i, '');
  return relative.split(path.sep).join('/');
}

function titleFromSlug(slug: string): string {
  const base = slug.split('/').pop() ?? slug;
  return base
    .split(/[-_]/)
    .filter((word) => word.length > 0)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function comparePages(a: Page, b: Page): number {
  if (a.frontmatter.date && b.frontmatter.date) {
    if (a.frontmatter.date !== b.frontmatter.date) {
      return a.frontmatter.date < b.frontmatter.date ? 1 : -1;
    }
  } else if (a.frontmatter.date) {
    return -1;
  } else if (b.frontmatter.date) {
    return 1;
  }
  return a.frontmatter.title.localeCompare(b.frontmatter.title);
}

/** Reads markdown content from contentDir, converts it to HTML, and writes the site to outputDir. */
export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const siteTitle = options.siteTitle ?? 'My Site';
  const templatesDir = options.templatesDir ?? './templates';

  if (!fs.existsSync(contentDir) || !fs.statSync(contentDir).isDirectory()) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const markdownFiles = findMarkdownFiles(contentDir).sort();

  const pages: Page[] = markdownFiles.map((filePath) => {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const slug = toSlug(contentDir, filePath);
    const { frontmatter, contentHtml } = parseMarkdown(raw, titleFromSlug(slug));
    return { slug, frontmatter, contentHtml, sourcePath: filePath };
  });

  pages.sort(comparePages);

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  const outputFiles: string[] = [];

  for (const page of pages) {
    const outputPath = path.join(outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, renderPageHtml(page, { templatesDir, siteTitle }), 'utf-8');
    outputFiles.push(outputPath);
  }

  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, renderIndexHtml(pages, siteTitle, { templatesDir }), 'utf-8');
  outputFiles.push(indexPath);

  const stylesheetPath = path.join(outputDir, 'style.css');
  fs.writeFileSync(stylesheetPath, DEFAULT_STYLESHEET, 'utf-8');
  outputFiles.push(stylesheetPath);

  return { pages, outputFiles };
}
