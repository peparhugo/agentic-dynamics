import { mkdirSync, readdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Page, pageFromFile } from './page';
import { indexHtml, pageHtml } from './templates';
import { loadTemplates } from './engine';

export const DEFAULT_TEMPLATES_DIR = './templates';

export function listMarkdownFiles(dir: string): string[] {
  const files: string[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      files.push(fullPath);
    }
  }
  return files;
}

export function buildSite(contentDir: string, outputDir: string, templatesDir: string = DEFAULT_TEMPLATES_DIR): Page[] {
  const files = listMarkdownFiles(contentDir);
  const pages = files.map(pageFromFile);
  pages.sort((a, b) => b.date.localeCompare(a.date));

  const engine = loadTemplates(templatesDir);

  mkdirSync(outputDir, { recursive: true });
  for (const page of pages) {
    const html = engine ? engine.renderPage(page) : pageHtml(page);
    writeFileSync(join(outputDir, `${page.slug}.html`), html, 'utf8');
  }
  const index = engine ? engine.renderIndex(pages) : indexHtml(pages);
  writeFileSync(join(outputDir, 'index.html'), index, 'utf8');
  return pages;
}
