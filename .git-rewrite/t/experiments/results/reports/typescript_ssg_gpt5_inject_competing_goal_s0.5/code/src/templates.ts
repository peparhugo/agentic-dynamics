import fs from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import fg from 'fast-glob';
import { TemplateRenderContext } from './types';

export type TemplateEnv = {
  renderPage: (layout: string, context: TemplateRenderContext) => string;
  defaultLayout: string;
};

export async function loadTemplates(templatesDir: string): Promise<TemplateEnv> {
  const hbs = Handlebars.create();

  // Helpers
  hbs.registerHelper('json', (v: any) => JSON.stringify(v));
  hbs.registerHelper('date', (v: any) => {
    const d = v instanceof Date ? v : new Date(String(v));
    if (isNaN(d.getTime())) return '';
    return d.toISOString();
  });
  hbs.registerHelper('eq', (a: any, b: any) => a === b);
  hbs.registerHelper('join', (arr: any[], sep: string) => Array.isArray(arr) ? arr.join(sep) : '');

  // Partials
  const partialFiles = await fg('partials/**/*.hbs', { cwd: templatesDir, dot: false });
  await Promise.all(partialFiles.map(async rel => {
    const name = rel.replace(/\\/g, '/').replace(/^partials\//, '').replace(/\.hbs$/i, '');
    const content = await fs.readFile(path.join(templatesDir, rel), 'utf8');
    hbs.registerPartial(name, content);
  }));

  // Layouts
  const layoutDir = path.join(templatesDir, 'layouts');
  const layoutFiles = await fg('layouts/**/*.hbs', { cwd: templatesDir, dot: false });
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  await Promise.all(layoutFiles.map(async rel => {
    const name = rel.replace(/\\/g, '/').replace(/^layouts\//, '').replace(/\.hbs$/i, '');
    const content = await fs.readFile(path.join(templatesDir, rel), 'utf8');
    layouts.set(name, hbs.compile(content));
  }));

  const defaultLayout = layouts.has('main') ? 'main' : (layouts.keys().next().value || 'main');

  function renderPage(layout: string, ctx: TemplateRenderContext): string {
    const lay = layouts.get(layout) || layouts.get(defaultLayout);
    if (!lay) throw new Error(`No layout found: ${layout}`);
    return lay(ctx);
  }

  return { renderPage, defaultLayout };
}
