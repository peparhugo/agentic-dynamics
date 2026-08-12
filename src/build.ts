import fs from 'fs';
import path from 'path';
import type { Page } from './parse';
import { readMarkdownFile } from './parse';
import { renderIndex, renderPage } from './template';

export interface BuildResult {
  pages: Page[];
  filesWritten: string[];
}

function collectMarkdownFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) {
    return files;
  }
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      files.push(full);
    }
  }
  return files;
}

export function buildSite(contentDir: string, outputDir: string): BuildResult {
  const files = collectMarkdownFiles(contentDir);
  const pages = files.map((f) => readMarkdownFile(f));
  pages.sort((a, b) => a.slug.localeCompare(b.slug));

  fs.mkdirSync(outputDir, { recursive: true });

  const filesWritten: string[] = [];

  for (const page of pages) {
    const filePath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(filePath, renderPage(page), 'utf8');
    filesWritten.push(filePath);
  }

  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, renderIndex(pages), 'utf8');
  filesWritten.push(indexPath);

  return { pages, filesWritten };
}
