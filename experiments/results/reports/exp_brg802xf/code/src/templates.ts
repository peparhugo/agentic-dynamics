import fs from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import fg from 'fast-glob';

export type TemplateEnv = {
  renderWithLayout: (bodyContext: any, options?: { layout?: string }) => string;
  renderPage: (templateName: string, context: any) => string;
};

export async function loadTemplates(templatesDir: string): Promise<TemplateEnv> {
  // Register partials from templates/partials/**/*.hbs
  const partialsDir = path.join(templatesDir, 'partials');
  const partialFiles = await fg('**/*.hbs', { cwd: partialsDir, dot: false, onlyFiles: true }).catch(() => []);
  for (const rel of partialFiles) {
    const full = path.join(partialsDir, rel);
    const name = toPartialName(rel);
    const src = await fs.readFile(full, 'utf8');
    Handlebars.registerPartial(name, src);
  }

  // Preload layouts into a map
  const layoutsDir = path.join(templatesDir, 'layouts');
  const layoutFiles = await fg('**/*.hbs', { cwd: layoutsDir, dot: false, onlyFiles: true }).catch(() => []);
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  for (const rel of layoutFiles) {
    const full = path.join(layoutsDir, rel);
    const name = toName(rel);
    const src = await fs.readFile(full, 'utf8');
    layouts.set(name, Handlebars.compile(src));
  }

  // Preload page templates
  const pagesDir = path.join(templatesDir, 'pages');
  const pageFiles = await fg('**/*.hbs', { cwd: pagesDir, dot: false, onlyFiles: true }).catch(() => []);
  const pages = new Map<string, Handlebars.TemplateDelegate>();
  for (const rel of pageFiles) {
    const full = path.join(pagesDir, rel);
    const name = toName(rel);
    const src = await fs.readFile(full, 'utf8');
    pages.set(name, Handlebars.compile(src));
  }

  // Minimal helpers
  Handlebars.registerHelper('join', function (this: any, arr: any[], sep: string) {
    return Array.isArray(arr) ? arr.join(sep) : '';
  });

  function renderWithLayout(bodyContext: any, options?: { layout?: string }) {
    const layoutName = options?.layout ?? 'default';
    const layout = layouts.get(layoutName);
    if (!layout) throw new Error(`Layout not found: ${layoutName}`);
    return layout(bodyContext);
  }

  function renderPage(templateName: string, context: any) {
    const page = pages.get(templateName) ?? pages.get('page');
    if (!page) throw new Error(`Page template not found: ${templateName}`);
    return page(context);
  }

  return { renderWithLayout, renderPage };
}

function toName(rel: string): string {
  return rel.replace(/\\/g, '/').replace(/\.hbs$/, '');
}

function toPartialName(rel: string): string {
  return toName(rel);
}
