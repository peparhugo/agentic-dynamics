import * as fs from 'fs';
import * as path from 'path';
import { parseFrontmatter } from './frontmatter';
import { markdownToHtml } from './markdown';
import { renderIndex, renderPage, SiteConfig } from './template';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  siteTitle?: string;
}

export const DEFAULT_CONTENT_DIR = './content';
export const DEFAULT_OUTPUT_DIR = './dist';
export const DEFAULT_SITE_TITLE = 'My Static Site';

const MARKDOWN_EXTENSION = /\.(md|markdown)$/i;

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) return [];

  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && MARKDOWN_EXTENSION.test(entry.name)) {
        files.push(full);
      }
    }
  };
  walk(contentDir);
  return files.sort();
}

export function slugFor(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath).replace(/\\/g, '/');
  return relative.replace(MARKDOWN_EXTENSION, '');
}

export async function buildSite(options: BuildOptions): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const config: SiteConfig = { title: options.siteTitle ?? DEFAULT_SITE_TITLE };

  const pages: Page[] = [];
  for (const file of collectMarkdownFiles(contentDir)) {
    const source = fs.readFileSync(file, 'utf8');
    const { data, content } = parseFrontmatter(source);
    const html = await markdownToHtml(content);
    const slug = slugFor(file, contentDir);
    pages.push({
      slug,
      link: `${slug}.html`,
      outputPath: path.join(outputDir, `${slug}.html`),
      filePath: file,
      data,
      content,
      html,
    });
  }

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    fs.mkdirSync(path.dirname(page.outputPath), { recursive: true });
    fs.writeFileSync(page.outputPath, renderPage(page, config), 'utf8');
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages, config), 'utf8');

  return pages;
}
