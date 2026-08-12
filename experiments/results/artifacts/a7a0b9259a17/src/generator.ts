import fs from 'fs';
import path from 'path';
import { ParseResult } from './types';
import { TemplateEngine } from './templates';

export function generateSite(
  { pages }: ParseResult,
  outputDir: string,
  templatesDir: string = './templates'
): void {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const engine = new TemplateEngine({ templatesDir });
  engine.init();

  for (const page of pages) {
    const html = engine.renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);
  }

  const indexHtml = engine.renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
}
