import fs from 'fs';
import path from 'path';
import { Page, BuildOptions } from './types';
import { parseMarkdown } from './parse';
import { renderIndex, renderPage } from './render';

export function collectPages(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }
  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  return entries
    .filter((e) => e.isFile() && e.name.endsWith('.md'))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => parseMarkdown(path.join(contentDir, e.name)));
}

export function buildSite(options: BuildOptions): Page[] {
  const { contentDir, outputDir } = options;

  const pages = collectPages(contentDir);

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), renderPage(page), 'utf-8');
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf-8');

  return pages;
}
