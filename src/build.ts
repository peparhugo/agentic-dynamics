import fs from 'fs';
import path from 'path';
import { parseMarkdownDirectory } from './parser';
import { generatePageHtml, generateIndexHtml } from './generator';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

export function build(options: BuildOptions): void {
  const { contentDir, outputDir } = options;

  const pages = parseMarkdownDirectory(contentDir);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = generatePageHtml(page);
    const outPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');
  }

  const indexHtml = generateIndexHtml(pages);
  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf-8');
}
