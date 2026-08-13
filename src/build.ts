import * as fs from 'fs';
import * as path from 'path';
import { findMarkdownFiles, parseMarkdownFile } from './parser';
import { renderIndex, renderPage, TemplateEngine } from './templates';
import { BuildOptions, BuildResult } from './types';

export function build(options: BuildOptions): BuildResult {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir || './templates');

  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const files = findMarkdownFiles(contentDir);
  const pages = files.map((file) => parseMarkdownFile(file, contentDir));

  const slugCounts = new Map<string, number>();
  for (const page of pages) {
    slugCounts.set(page.slug, (slugCounts.get(page.slug) || 0) + 1);
  }
  const duplicates = [...slugCounts.entries()].filter(([, count]) => count > 1);
  if (duplicates.length > 0) {
    const names = duplicates.map(([slug]) => slug).join(', ');
    throw new Error(`Duplicate page slug(s) detected: ${names}`);
  }

  const engine = new TemplateEngine(templatesDir);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const outFile = path.join(outputDir, page.outputPath);
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, renderPage(page, engine), 'utf-8');
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages, engine), 'utf-8');

  return { pages, outputDir };
}
