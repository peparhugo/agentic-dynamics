import fs from 'fs';
import path from 'path';
import { Page } from './types';
import { TemplateEngine } from './templates';

export function generateSite(pages: Page[], outputDir: string, templatesDir?: string): void {
  const resolved = path.resolve(outputDir);
  fs.mkdirSync(resolved, { recursive: true });

  const engine = new TemplateEngine(templatesDir || './templates');

  for (const page of pages) {
    const body = engine.renderPage(page);
    const html = engine.renderLayout(page.frontmatter.title, body, page.frontmatter.layout);
    fs.writeFileSync(path.join(resolved, `${page.slug}.html`), html, 'utf-8');
  }

  const indexBody = engine.renderIndex(pages);
  const indexHtml = engine.renderLayout('Site Index', indexBody);
  fs.writeFileSync(path.join(resolved, 'index.html'), indexHtml, 'utf-8');
}
