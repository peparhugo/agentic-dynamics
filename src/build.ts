import fs from 'fs';
import path from 'path';
import { parseMarkdown, renderMarkdown } from './parser';
import { buildPageHtml, buildIndexHtml, pageTitle } from './generator';
import { TemplateEngine } from './engine';
import type { SiteContext } from './engine';
import type { Page } from './types';

export interface SiteBuildResult {
  outputDir: string;
  pages: Page[];
  indexFile: string;
}

export function slugify(fileName: string): string {
  const slug = fileName
    .toLowerCase()
    .replace(/\.[^.]+$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'page';
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = 'templates',
): SiteBuildResult {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`content directory not found: ${contentDir}`);
  }

  const mdFiles = fs
    .readdirSync(contentDir)
    .filter((f) => {
      if (!fs.statSync(path.join(contentDir, f)).isFile()) return false;
      return f.toLowerCase().endsWith('.md');
    })
    .sort();

  if (mdFiles.length === 0) {
    throw new Error(`no markdown files found in: ${contentDir}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const pages: Page[] = mdFiles.map((file) => {
    const raw = fs.readFileSync(path.join(contentDir, file), 'utf-8');
    const { data, body } = parseMarkdown(raw);
    const slug = slugify(file);
    return {
      slug,
      sourcePath: file,
      data,
      body,
      html: renderMarkdown(body),
      outputFile: slug === 'index' ? 'index-page.html' : `${slug}.html`,
    };
  });

  pages.sort((a, b) => {
    const dateA = a.data.date ? String(a.data.date) : '';
    const dateB = b.data.date ? String(b.data.date) : '';
    if (dateA !== dateB) {
      return dateA > dateB ? -1 : 1;
    }
    return a.slug.localeCompare(b.slug);
  });

  const engine = fs.existsSync(templatesDir) ? new TemplateEngine(templatesDir) : null;
  const site: SiteContext = {
    pages: pages.map((page) => ({
      slug: page.slug,
      title: pageTitle(page.data, page.slug),
      outputFile: page.outputFile,
      date: page.data.date !== undefined ? String(page.data.date) : undefined,
    })),
  };

  for (const page of pages) {
    const templated = engine ? engine.renderPage(page, site) : null;
    const html = templated !== null ? templated : buildPageHtml(page);
    fs.writeFileSync(path.join(outputDir, page.outputFile), html, 'utf-8');
  }

  const indexFile = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexFile, buildIndexHtml(pages), 'utf-8');

  return { outputDir, pages, indexFile };
}
