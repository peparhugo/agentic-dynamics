import fs from 'fs';
import path from 'path';
import { Page, BuildResult } from './types';
import { parseMarkdown } from './markdown';
import {
  TemplateEngine,
  DEFAULT_TEMPLATES_DIR,
  renderPage,
  renderIndex,
} from './template';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

export { renderPage, renderIndex } from './template';

export function findMarkdownFiles(contentDir: string): string[] {
  const results: string[] = [];
  const walk = (dir: string): void => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && /\.mdx?$/i.test(entry.name)) {
        results.push(full);
      }
    }
  };
  walk(contentDir);
  results.sort();
  return results;
}

export function readPages(contentDir: string): Page[] {
  const files = findMarkdownFiles(contentDir);
  return files.map((file) =>
    parseMarkdown(fs.readFileSync(file, 'utf8'), path.relative(contentDir, file))
  );
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.date ? new Date(a.date).getTime() : 0;
    const db = b.date ? new Date(b.date).getTime() : 0;
    if (da !== db) return db - da;
    return a.title.localeCompare(b.title);
  });
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir: string = DEFAULT_TEMPLATES_DIR
): BuildResult {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`content directory not found: ${contentDir}`);
  }
  const pages = sortPages(readPages(contentDir));
  const engine = new TemplateEngine(templatesDir);
  fs.mkdirSync(outputDir, { recursive: true });

  const files: string[] = [];
  for (const page of pages) {
    const name = `${page.slug}.html`;
    fs.writeFileSync(path.join(outputDir, name), renderPage(page, engine), 'utf8');
    files.push(name);
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages, engine), 'utf8');
  files.push('index.html');

  return { pages: pages.length, outputDir, files };
}
