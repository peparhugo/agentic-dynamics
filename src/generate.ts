import fs from 'fs';
import path from 'path';
import { BuildOptions, Page } from './types';
import { loadPages } from './markdown';
import { TemplateEngine } from './templates';

export function build(options: BuildOptions): Page[] {
  const pages = loadPages(options.contentDir);
  const outputDir = options.outputDir;
  const templatesDir = options.templatesDir ?? './templates';
  fs.mkdirSync(outputDir, { recursive: true });

  const engine = new TemplateEngine(templatesDir);

  for (const page of pages) {
    const html = engine.renderPage(page, pages);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html, 'utf-8');
  }

  const indexHtml = engine.renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');

  return pages;
}
