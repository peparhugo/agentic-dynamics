import fs from 'fs-extra';
import path from 'node:path';
import Handlebars from 'handlebars';

type Compiled = Handlebars.TemplateDelegate<any>;

export type TemplateEnv = {
  renderTemplate: (name: string, data: any) => string;
  renderWithLayout: (templateName: string, layoutName: string | undefined, data: any) => string;
};

export async function loadTemplates(templatesDir: string): Promise<TemplateEnv> {
  // Register partials from templates/partials
  const partialsDir = path.join(templatesDir, 'partials');
  if (await fs.pathExists(partialsDir)) {
    const files = await fs.readdir(partialsDir);
    for (const f of files) {
      if (!f.endsWith('.hbs')) continue;
      const name = path.basename(f, '.hbs');
      const content = await fs.readFile(path.join(partialsDir, f), 'utf8');
      Handlebars.registerPartial(name, content);
    }
  }

  // Load all top-level templates (*.hbs)
  const entries = await fs.readdir(templatesDir);
  const templates = new Map<string, Compiled>();
  for (const e of entries) {
    if (!e.endsWith('.hbs')) continue;
    const name = path.basename(e, '.hbs');
    const content = await fs.readFile(path.join(templatesDir, e), 'utf8');
    templates.set(name, Handlebars.compile(content));
  }

  // Load layouts
  const layoutsDir = path.join(templatesDir, 'layouts');
  const layouts = new Map<string, Compiled>();
  if (await fs.pathExists(layoutsDir)) {
    const files = await fs.readdir(layoutsDir);
    for (const f of files) {
      if (!f.endsWith('.hbs')) continue;
      const name = path.basename(f, '.hbs');
      const content = await fs.readFile(path.join(layoutsDir, f), 'utf8');
      layouts.set(name, Handlebars.compile(content));
    }
  }

  function renderTemplate(name: string, data: any): string {
    const t = templates.get(name);
    if (!t) throw new Error(`Template not found: ${name}`);
    return t(data);
  }
  function renderWithLayout(templateName: string, layoutName: string | undefined, data: any): string {
    const inner = renderTemplate(templateName, data);
    const layout = layoutName ?? 'layout';
    const lay = layouts.get(layout);
    if (!lay) return inner; // if no layout, return template output directly
    return lay({ ...data, body: inner });
  }

  // Some simple helpers that are commonly useful
  Handlebars.registerHelper('date', function (value: any) {
    const d = value instanceof Date ? value : new Date(value);
    return d.toISOString();
  });
  Handlebars.registerHelper('json', function (value: any) {
    return JSON.stringify(value);
  });

  return { renderTemplate, renderWithLayout };
}
