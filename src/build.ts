import fs from 'fs';
import path from 'path';
import { Page, BuildOptions } from './types';
import { parseMarkdown } from './parse';
import { renderIndex, renderPage } from './render';
import { createTemplateEngine, TemplateEngine } from './templates';

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

function resolveTemplatesDir(contentDir: string, templatesDir?: string): string {
  return templatesDir ?? path.join(path.dirname(contentDir), 'templates');
}

function loadEngine(templatesDir: string): TemplateEngine | null {
  return fs.existsSync(templatesDir) ? createTemplateEngine(templatesDir) : null;
}

export function buildSite(options: BuildOptions): Page[] {
  const { contentDir, outputDir } = options;

  const pages = collectPages(contentDir);
  const engine = loadEngine(resolveTemplatesDir(contentDir, options.templatesDir));

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = engine ? (engine.renderPage(page) ?? renderPage(page)) : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html, 'utf-8');
  }

  const indexHtml = engine ? (engine.renderIndex(pages) ?? renderIndex(pages)) : renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');

  return pages;
}
