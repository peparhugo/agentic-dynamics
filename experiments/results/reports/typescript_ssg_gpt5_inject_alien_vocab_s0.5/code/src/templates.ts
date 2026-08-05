import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';

export type Templates = {
  renderPage: (templateName: string, layoutName: string, ctx: any) => string;
  hasTemplate: (name: string) => boolean;
  hasLayout: (name: string) => boolean;
};

export function loadTemplates(templatesDir: string): Templates {
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');

  const hbs = Handlebars.create();

  // Minimal helpers
  hbs.registerHelper('json', (v: any) => JSON.stringify(v));
  hbs.registerHelper('formatDate', (v: any) => {
    try {
      const d = typeof v === 'string' ? new Date(v) : v;
      return d instanceof Date && !isNaN(d.getTime()) ? d.toISOString().substring(0, 10) : '';
    } catch {
      return '';
    }
  });

  // Register partials
  if (fs.existsSync(partialsDir)) {
    for (const file of fs.readdirSync(partialsDir)) {
      if (file.endsWith('.hbs')) {
        const name = file.replace(/\.hbs$/, '');
        const tpl = fs.readFileSync(path.join(partialsDir, file), 'utf8');
        hbs.registerPartial(name, tpl);
      }
    }
  }

  // Load templates and layouts
  const templateMap = new Map<string, Handlebars.TemplateDelegate>();
  const layoutMap = new Map<string, Handlebars.TemplateDelegate>();

  for (const file of fs.readdirSync(templatesDir)) {
    if (file.endsWith('.hbs')) {
      const name = file.replace(/\.hbs$/, '');
      const tpl = fs.readFileSync(path.join(templatesDir, file), 'utf8');
      templateMap.set(name, hbs.compile(tpl));
    }
  }

  if (fs.existsSync(layoutsDir)) {
    for (const file of fs.readdirSync(layoutsDir)) {
      if (file.endsWith('.hbs')) {
        const name = file.replace(/\.hbs$/, '');
        const tpl = fs.readFileSync(path.join(layoutsDir, file), 'utf8');
        layoutMap.set(name, hbs.compile(tpl));
      }
    }
  }

  const renderPage = (templateName: string, layoutName: string, ctx: any) => {
    const pageTpl = templateMap.get(templateName);
    if (!pageTpl) throw new Error(`Template not found: ${templateName}`);
    const body = pageTpl(ctx);
    const layoutTpl = layoutMap.get(layoutName);
    if (!layoutTpl) return body; // allow no layout
    return layoutTpl({ ...ctx, body });
  };

  return {
    renderPage,
    hasTemplate: (n) => templateMap.has(n),
    hasLayout: (n) => layoutMap.has(n)
  };
}
