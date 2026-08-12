import { promises as fs } from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

import type { Page } from './types';

export interface TemplateEngine {
  templateDir: string;
  pageTemplates: Map<string, string>;
  layouts: Map<string, string>;
  environment: typeof Handlebars;
}

export interface FallbackRenderers {
  document(page: Page, content: string): string;
  indexBody(pages: Page[]): string;
  indexDocument(pages: Page[]): string;
}

function templateName(filePath: string): string {
  return path.basename(filePath).replace(/\.hbs$/i, '');
}

async function readHbsMap(dir: string): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return map;
  }
  for (const entry of entries) {
    if (entry.isFile() && /\.hbs$/i.test(entry.name)) {
      const source = await fs.readFile(path.join(dir, entry.name), 'utf8');
      map.set(templateName(entry.name), source);
    }
  }
  return map;
}

export async function loadTemplateEngine(templateDir: string): Promise<TemplateEngine | null> {
  const [pageTemplates, layouts, partials] = await Promise.all([
    readHbsMap(templateDir),
    readHbsMap(path.join(templateDir, 'layouts')),
    readHbsMap(path.join(templateDir, 'partials')),
  ]);
  if (pageTemplates.size === 0 && layouts.size === 0 && partials.size === 0) {
    return null;
  }
  const environment = Handlebars.create();
  for (const [name, source] of partials) {
    environment.registerPartial(name, source);
  }
  return { templateDir, pageTemplates, layouts, environment };
}

export function renderTemplate(
  engine: TemplateEngine,
  source: string,
  context: Record<string, unknown>
): string {
  return engine.environment.compile(source)(context);
}

export function pageContext(page: Page): Record<string, unknown> {
  return {
    ...(page.data ?? {}),
    page,
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.content,
    html: page.html,
  };
}

export function renderPageWithTemplates(
  page: Page,
  engine: TemplateEngine,
  fallbacks: FallbackRenderers
): string {
  const context = pageContext(page);
  let content = page.html;

  if (page.template !== undefined) {
    const source = engine.pageTemplates.get(page.template);
    if (source === undefined) {
      throw new Error(`Template not found: ${page.template}`);
    }
    content = renderTemplate(engine, source, context);
  } else if (engine.pageTemplates.has('default')) {
    content = renderTemplate(engine, engine.pageTemplates.get('default')!, context);
  }

  const layoutName = page.layout ?? 'default';
  const layout = engine.layouts.get(layoutName);
  if (layout !== undefined) {
    return renderTemplate(engine, layout, { ...context, body: content });
  }
  if (page.layout !== undefined) {
    throw new Error(`Layout not found: ${page.layout}`);
  }
  return fallbacks.document(page, content);
}

export function renderIndexWithTemplates(
  pages: Page[],
  engine: TemplateEngine,
  fallbacks: FallbackRenderers
): string {
  const context: Record<string, unknown> = { pages, pageCount: pages.length, title: 'Index' };
  const body = engine.pageTemplates.has('index')
    ? renderTemplate(engine, engine.pageTemplates.get('index')!, context)
    : fallbacks.indexBody(pages);
  const layout = engine.layouts.get('default');
  if (layout !== undefined) {
    return renderTemplate(engine, layout, { ...context, body });
  }
  if (engine.pageTemplates.has('index')) {
    return body;
  }
  return fallbacks.indexDocument(pages);
}
