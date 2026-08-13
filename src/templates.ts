import * as path from 'path';
import { Page } from './types';
import { escapeHtml, TemplateEngine } from './templateEngine';

export { escapeHtml };

const DEFAULT_TEMPLATES_DIR = './templates';

const engineCache = new Map<string, TemplateEngine>();

function getEngine(templatesDir: string): TemplateEngine {
  const resolved = path.resolve(templatesDir);
  let engine = engineCache.get(resolved);
  if (!engine) {
    engine = new TemplateEngine(templatesDir);
    engineCache.set(resolved, engine);
  }
  return engine;
}

function basePathFor(slug: string): string {
  return '../'.repeat(slug.split('/').length - 1);
}

function metaHtml(page: Page): string {
  const parts: string[] = [];
  if (page.frontmatter.date) {
    parts.push(`<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>`);
  }
  if (page.frontmatter.tags.length > 0) {
    const tags = page.frontmatter.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
    parts.push(`<span class="tags">${tags}</span>`);
  }
  return parts.length > 0 ? `<p class="meta">${parts.join(' &middot; ')}</p>` : '';
}

export interface RenderPageOptions {
  /** Directory holding page/index templates, layouts/, and partials/. Defaults to './templates'. */
  templatesDir?: string;
  /** Site-wide title shown in the header/footer partials. Defaults to the page's own title. */
  siteTitle?: string;
}

export interface RenderIndexOptions {
  /** Directory holding page/index templates, layouts/, and partials/. Defaults to './templates'. */
  templatesDir?: string;
}

/** Renders a single content page using its frontmatter-selected template and layout (or the defaults). */
export function renderPageHtml(page: Page, options: RenderPageOptions = {}): string {
  const engine = getEngine(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const basePath = basePathFor(page.slug);
  const title = escapeHtml(page.frontmatter.title);
  const siteTitle = escapeHtml(options.siteTitle ?? page.frontmatter.title);

  return engine.render(
    page.frontmatter.template ?? 'page',
    page.frontmatter.layout ?? 'default',
    { title, meta: metaHtml(page), content: page.contentHtml, basePath },
    { title, siteTitle, basePath }
  );
}

/** Renders the site index listing using the 'index' template wrapped in the default layout. */
export function renderIndexHtml(pages: Page[], siteTitle: string, options: RenderIndexOptions = {}): string {
  const engine = getEngine(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const escapedSiteTitle = escapeHtml(siteTitle);
  const items = pages.map((page) => ({
    title: escapeHtml(page.frontmatter.title),
    href: escapeHtml(`${page.slug}.html`),
    meta: metaHtml(page),
  }));

  return engine.render(
    'index',
    'default',
    { pages: items, siteTitle: escapedSiteTitle },
    { title: escapedSiteTitle, siteTitle: escapedSiteTitle, basePath: '' }
  );
}

export const DEFAULT_STYLESHEET = `body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }
a { color: #0b5fff; }
header h1 { font-size: 1.25rem; }
header h1 a { text-decoration: none; color: inherit; }
nav { margin-bottom: 1.5rem; font-size: 0.875rem; }
footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #eee; color: #666; font-size: 0.8rem; }
.page-list { list-style: none; padding: 0; }
.page-list li { margin-bottom: 1.25rem; }
.meta { color: #666; font-size: 0.875rem; margin: 0.25rem 0; }
.tag { background: #eee; border-radius: 0.25rem; padding: 0.1rem 0.4rem; font-size: 0.75rem; }
.post-label { text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.75rem; color: #0b5fff; margin: 0; }
`;
