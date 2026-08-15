/**
 * Template engine support built on Handlebars.
 *
 * Expected directory layout:
 *
 *   templates/            page templates; `default.hbs` is used when a page
 *                         does not declare a template in its frontmatter
 *   templates/layouts/    layout templates that wrap page output through the
 *                         `{{{body}}}` placeholder
 *   templates/partials/   reusable partials (e.g. header, footer, nav)
 *
 * Pages may declare a `template` and a `layout` in their frontmatter, either
 * with or without the `.hbs` extension. If a templates directory exists, every
 * page is rendered through its template and then wrapped in its layout; the
 * site index uses `index.hbs` (falling back to the built-in index renderer).
 */

import fs from 'fs';
import path from 'path';

import Handlebars from 'handlebars';

import type { Page } from './types';

/** Name of the template used when a page does not declare one. */
export const DEFAULT_TEMPLATE = 'default';
/** Name of the layout used when a page does not declare one. */
export const DEFAULT_LAYOUT = 'default';
/** Default directory searched for templates, layouts and partials. */
export const DEFAULT_TEMPLATES_DIR = 'templates';
/** File extension used by template files. */
export const TEMPLATE_EXTENSION = 'hbs';

/** Loaded and compiled template assets. */
export interface Templates {
  /** Path of the templates directory these were loaded from. */
  dir: string;
  /** Compiled page templates keyed by file name. */
  templates: Map<string, Handlebars.TemplateDelegate>;
  /** Compiled layout templates keyed by file name. */
  layouts: Map<string, Handlebars.TemplateDelegate>;
  /** Compiled partials keyed by name (file name without extension). */
  partials: Map<string, Handlebars.TemplateDelegate>;
}

/** Context available to templates and layouts while rendering a page. */
export interface TemplateContext extends Record<string, unknown> {
  title: string;
  date?: string;
  tags: string[];
  /** Rendered Markdown body of the page. */
  body: string;
  /** Raw Markdown body of the page. */
  content: string;
  slug: string;
  outputName: string;
}

/** List `.hbs` template files (non-recursive) inside a directory. */
function listTemplateFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isFile() &&
        new RegExp(`\\.${TEMPLATE_EXTENSION}$`, 'i').test(entry.name),
    )
    .map((entry) => entry.name)
    .sort();
}

/** Whether a templates directory exists at the given path. */
export function hasTemplates(templatesDir: string): boolean {
  return fs.existsSync(templatesDir);
}

/**
 * Load every template, layout and partial found under `templatesDir`.
 * Partials are registered on a private Handlebars environment keyed by their
 * file name without the extension, so templates and layouts can reference them
 * with `{{> name}}`.
 */
export function loadTemplates(templatesDir: string): Templates {
  const engine = Handlebars.create();

  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  const partials = new Map<string, Handlebars.TemplateDelegate>();

  for (const name of listTemplateFiles(templatesDir)) {
    templates.set(
      name,
      engine.compile(fs.readFileSync(path.join(templatesDir, name), 'utf8')),
    );
  }

  const layoutsDir = path.join(templatesDir, 'layouts');
  for (const name of listTemplateFiles(layoutsDir)) {
    layouts.set(
      name,
      engine.compile(fs.readFileSync(path.join(layoutsDir, name), 'utf8')),
    );
  }

  const partialsDir = path.join(templatesDir, 'partials');
  for (const name of listTemplateFiles(partialsDir)) {
    const compiled = engine.compile(
      fs.readFileSync(path.join(partialsDir, name), 'utf8'),
    );
    const partialName = path.basename(name, path.extname(name));
    partials.set(partialName, compiled);
    engine.registerPartial(partialName, compiled);
  }

  return { dir: templatesDir, templates, layouts, partials };
}

/** Normalise a template/layout name into a file name with an extension. */
export function resolveTemplateName(
  name: string,
  extension = TEMPLATE_EXTENSION,
): string {
  const trimmed = name.trim();
  return new RegExp(`\\.${extension}$`, 'i').test(trimmed)
    ? trimmed
    : `${trimmed}.${extension}`;
}

/** Build the render context for a page. */
export function pageContext(page: Page): TemplateContext {
  return {
    ...page.data,
    title: page.title,
    date: page.date,
    tags: page.tags,
    body: page.html,
    content: page.content,
    slug: page.slug,
    outputName: page.outputName,
  };
}

/** Render a compiled template file from the templates or layouts directory. */
export function renderTemplateFile(
  templates: Templates,
  kind: 'templates' | 'layouts',
  name: string,
  context: Record<string, unknown>,
): string {
  const compiled =
    kind === 'layouts' ? templates.layouts.get(name) : templates.templates.get(name);
  if (!compiled) {
    throw new Error(`Template not found: ${kind}/${name}`);
  }
  return compiled(context);
}

/** Resolve the template file a page should use, falling back to the default. */
function pageTemplateName(page: Page): string {
  const declared = page.data.template;
  const name =
    typeof declared === 'string' && declared.trim() ? declared : DEFAULT_TEMPLATE;
  return resolveTemplateName(name);
}

/** Resolve the layout file a page should use, falling back to the default. */
function pageLayoutName(page: Page): string {
  const declared = page.data.layout;
  const name =
    typeof declared === 'string' && declared.trim() ? declared : DEFAULT_LAYOUT;
  return resolveTemplateName(name);
}

/**
 * Render a full page: first through its page template, then wrapped in its
 * layout using the `{{{body}}}` placeholder.
 */
export function renderPageWithTemplates(page: Page, templates: Templates): string {
  const context = pageContext(page);

  const content = renderTemplateFile(
    templates,
    'templates',
    pageTemplateName(page),
    context,
  );
  return renderTemplateFile(templates, 'layouts', pageLayoutName(page), {
    ...context,
    body: content,
  });
}

/** Render the site index through the `index` template and the default layout. */
export function renderIndexWithTemplates(pages: Page[], templates: Templates): string {
  const context = {
    title: 'Index',
    pages: pages.map((page) => pageContext(page)),
  };

  const body = renderTemplateFile(
    templates,
    'templates',
    `index.${TEMPLATE_EXTENSION}`,
    context,
  );
  return renderTemplateFile(templates, 'layouts', resolveTemplateName(DEFAULT_LAYOUT), {
    ...context,
    body,
  });
}
