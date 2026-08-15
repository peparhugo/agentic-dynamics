import fs from 'fs';
import path from 'path';
import { BuildOptions, Page } from './types';
import { loadPages } from './markdown';
import { renderIndex, renderPage } from './templates';

export function build(options: BuildOptions): Page[] {
  const pages = loadPages(options.contentDir);
  const outputDir = options.outputDir;
  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = renderPage(page, pages);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html, 'utf-8');
  }

  const indexHtml = renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');

  return pages;
}
