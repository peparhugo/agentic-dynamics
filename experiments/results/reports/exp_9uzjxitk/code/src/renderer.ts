import fs from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Post, SiteConfig, TemplateContext } from './types.js';

export interface Templates {
  layouts: Record<string, Handlebars.TemplateDelegate>;
  pages: Record<string, Handlebars.TemplateDelegate>;
}

export function loadTemplates(templateDir: string): Templates {
  const layouts: Record<string, Handlebars.TemplateDelegate> = {};
  const pages: Record<string, Handlebars.TemplateDelegate> = {};

  const partialsDir = path.join(templateDir, 'partials');
  if (fs.existsSync(partialsDir)) {
    for (const file of fs.readdirSync(partialsDir)) {
      if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
        const name = path.basename(file, path.extname(file));
        const source = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
        Handlebars.registerPartial(name, source);
      }
    }
  }

  const layoutsDir = path.join(templateDir, 'layouts');
  if (fs.existsSync(layoutsDir)) {
    for (const file of fs.readdirSync(layoutsDir)) {
      if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
        const name = path.basename(file, path.extname(file));
        const source = fs.readFileSync(path.join(layoutsDir, file), 'utf-8');
        layouts[name] = Handlebars.compile(source);
      }
    }
  }

  const pagesDir = templateDir;
  for (const entry of fs.readdirSync(pagesDir, { withFileTypes: true })) {
    if (
      entry.isFile() &&
      (entry.name.endsWith('.hbs') || entry.name.endsWith('.handlebars'))
    ) {
      const name = path.basename(entry.name, path.extname(entry.name));
      const source = fs.readFileSync(path.join(pagesDir, entry.name), 'utf-8');
      pages[name] = Handlebars.compile(source);
    }
  }

  return { layouts, pages };
}

export function renderPage(
  templates: Templates,
  templateName: string,
  context: TemplateContext,
): string {
  const pageTemplate = templates.pages[templateName];
  if (!pageTemplate) {
    throw new Error(`Template "${templateName}" not found. Available: ${Object.keys(templates.pages).join(', ')}`);
  }

  const innerHtml = pageTemplate(context);

  const layoutName = context.page?.frontmatter?.layout || 'default';
  const layout = templates.layouts[layoutName];
  if (layout) {
    return layout({ ...context, body: innerHtml, content: innerHtml });
  }

  return innerHtml;
}

Handlebars.registerHelper('dateFormat', function (dateStr: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
});

Handlebars.registerHelper('eq', function (a: unknown, b: unknown) {
  return a === b;
});

Handlebars.registerHelper('encodeURI', function (str: string) {
  return encodeURIComponent(str);
});
