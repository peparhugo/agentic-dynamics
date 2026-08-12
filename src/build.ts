import { mkdirSync, readdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Page, pageFromFile } from './page';
import { indexHtml, pageHtml } from './templates';

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

export function buildSite(contentDir: string, outputDir: string): Page[] {
  const files = listMarkdownFiles(contentDir);
  const pages = files.map(pageFromFile);
  pages.sort((a, b) => b.date.localeCompare(a.date));

  mkdirSync(outputDir, { recursive: true });
  for (const page of pages) {
    writeFileSync(join(outputDir, `${page.slug}.html`), pageHtml(page), 'utf8');
  }
  writeFileSync(join(outputDir, 'index.html'), indexHtml(pages), 'utf8');
  return pages;
}
