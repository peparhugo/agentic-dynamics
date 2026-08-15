import { promises as fs } from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

const TEMPLATE_EXTENSIONS = ['.hbs'];
const DEFAULT_TEMPLATE_NAME = 'default';
const DEFAULT_LAYOUT_NAME = 'default';
const INDEX_TEMPLATE_NAME = 'index';

export interface TemplateBundle {
  exists: boolean;
  hbs: typeof Handlebars;
  templates: Map<string, Handlebars.TemplateDelegate>;
  layouts: Map<string, Handlebars.TemplateDelegate>;
  partials: Map<string, Handlebars.TemplateDelegate>;
  defaultTemplate: string | null;
  defaultLayout: string | null;
  hasIndexTemplate: boolean;
}

async function dirExists(dir: string): Promise<boolean> {
  try {
    const stat = await fs.stat(dir);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

async function readTemplateMap(
  dir: string,
  hbs: typeof Handlebars
): Promise<Map<string, Handlebars.TemplateDelegate>> {
  const map = new Map<string, Handlebars.TemplateDelegate>();
  if (!(await dirExists(dir))) {
    return map;
  }
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) {
      continue;
    }
    const ext = path.extname(entry.name).toLowerCase();
    if (!TEMPLATE_EXTENSIONS.includes(ext)) {
      continue;
    }
    const name = entry.name.slice(0, -ext.length);
    const source = await fs.readFile(path.join(dir, entry.name), 'utf8');
    map.set(name, hbs.compile(source));
  }
  return map;
}

/**
 * Load the template tree at `templatesDir`.
 *
 * Expected layout:
 *   ./templates/            page templates (.hbs)
 *   ./templates/layouts/    layout templates (.hbs)
 *   ./templates/partials/   reusable partials (.hbs)
 *
 * `default.hbs` is used when a page does not name a template and
 * `layouts/default.hbs` wraps every rendered page unless the page opts out
 * via a `layout:` frontmatter field.
 */
export async function loadTemplates(templatesDir: string): Promise<TemplateBundle> {
  const exists = await dirExists(templatesDir);
  if (!exists) {
    return {
      exists: false,
      hbs: Handlebars.create(),
      templates: new Map(),
      layouts: new Map(),
      partials: new Map(),
      defaultTemplate: null,
      defaultLayout: null,
      hasIndexTemplate: false,
    };
  }

  const hbs = Handlebars.create();
  const templates = await readTemplateMap(templatesDir, hbs);
  const layouts = await readTemplateMap(path.join(templatesDir, 'layouts'), hbs);
  const partials = await readTemplateMap(path.join(templatesDir, 'partials'), hbs);

  for (const [name, template] of partials) {
    hbs.registerPartial(name, template);
  }

  return {
    exists: true,
    hbs,
    templates,
    layouts,
    partials,
    defaultTemplate: templates.has(DEFAULT_TEMPLATE_NAME) ? DEFAULT_TEMPLATE_NAME : null,
    defaultLayout: layouts.has(DEFAULT_LAYOUT_NAME) ? DEFAULT_LAYOUT_NAME : null,
    hasIndexTemplate: templates.has(INDEX_TEMPLATE_NAME),
  };
}

function normalizeTemplateName(value: string): string {
  let name = value.trim().replace(/\\/g, '/').split('/').pop() || '';
  for (const ext of TEMPLATE_EXTENSIONS) {
    if (name.toLowerCase().endsWith(ext)) {
      name = name.slice(0, -ext.length);
      break;
    }
  }
  return name;
}

function makePageContext(page: Page): Record<string, unknown> {
  return {
    page,
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.content,
    html: page.html,
    ...page.data,
  };
}

function resolveLayoutName(page: Page, bundle: TemplateBundle): string | null {
  if (page.layout) {
    return normalizeTemplateName(page.layout);
  }
  return bundle.defaultLayout;
}

/**
 * Render a single page through its template and layout. Throws when a page
 * explicitly names a template or layout that cannot be found.
 */
export function renderPageTemplate(page: Page, bundle: TemplateBundle): string {
  if (!bundle.exists) {
    throw new Error('templates directory not found');
  }

  let templateName = bundle.defaultTemplate;
  if (page.template) {
    templateName = normalizeTemplateName(page.template);
  }

  const template = templateName ? bundle.templates.get(templateName) : undefined;
  if (!template) {
    throw new Error(`template not found: ${templateName}`);
  }

  const context = makePageContext(page);
  const body = template(context);

  const layoutName = resolveLayoutName(page, bundle);
  const layout = layoutName ? bundle.layouts.get(layoutName) : undefined;
  if (layoutName && !layout) {
    throw new Error(`layout not found: ${layoutName}`);
  }

  if (layout) {
    return layout({ ...context, body });
  }
  return body;
}

/**
 * Render the site index from `index.hbs` when present, otherwise return null
 * so callers can fall back to the built-in index renderer.
 */
export function renderIndexTemplate(
  pages: Page[],
  bundle: TemplateBundle
): string | null {
  if (!bundle.exists || !bundle.hasIndexTemplate) {
    return null;
  }

  const template = bundle.templates.get(INDEX_TEMPLATE_NAME);
  if (!template) {
    return null;
  }

  const context: Record<string, unknown> = { pages, site: { pages } };
  const body = template(context);

  const layoutName = bundle.defaultLayout;
  const layout = layoutName ? bundle.layouts.get(layoutName) : undefined;
  if (layout) {
    return layout({ ...context, body });
  }
  return body;
}
