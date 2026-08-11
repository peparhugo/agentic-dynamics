import fs from 'fs';
import path from 'path';
import { parseMarkdownDirectory } from './parser';
import { generatePageHtml, generateIndexHtml } from './generator';
import { TemplateEngine } from './templates';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export function build(options: BuildOptions): void {
  const { contentDir, outputDir, templatesDir } = options;

  const pages = parseMarkdownDirectory(contentDir);

  let engine: TemplateEngine | undefined;
  if (templatesDir) {
    engine = new TemplateEngine();
    engine.init(templatesDir);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = generatePageHtml(page, engine);
    const outPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');
  }

  const indexHtml = generateIndexHtml(pages, engine);
  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf-8');
}
