import { readFile } from 'fs/promises';
import { join, extname } from 'path';
import { readdirSync } from 'fs';
import Handlebars from 'handlebars';
import { Post, SiteConfig } from './types.js';

type CompiledTemplate = (context: Record<string, unknown>) => string;

export async function loadTemplates(
  templatesDir: string,
): Promise<{ templates: Map<string, CompiledTemplate>; layout: CompiledTemplate | null }> {
  const templates = new Map<string, CompiledTemplate>();
  let layout: CompiledTemplate | null = null;

  const partialsDir = join(templatesDir, 'partials');
  try {
    const partialFiles = readdirSync(partialsDir);
    for (const file of partialFiles) {
      if (extname(file) === '.hbs') {
        const content = await readFile(join(partialsDir, file), 'utf-8');
        const name = file.replace('.hbs', '');
        Handlebars.registerPartial(name, content);
      }
    }
  } catch {
    // no partials directory, ignore
  }

  const entries = readdirSync(templatesDir);
  for (const file of entries) {
    if (extname(file) !== '.hbs') continue;
    const content = await readFile(join(templatesDir, file), 'utf-8');
    const compiled = Handlebars.compile(content) as CompiledTemplate;
    const name = file.replace('.hbs', '');
    if (name === 'layout') {
      layout = compiled;
    } else {
      templates.set(name, compiled);
    }
  }

  return { templates, layout };
}

export function registerHelpers(site: SiteConfig): void {
  Handlebars.registerHelper('dateFormat', function (date: string) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  });

  Handlebars.registerHelper('rssDate', function (date: string) {
    if (!date) return '';
    return new Date(date).toUTCString();
  });

  Handlebars.registerHelper('tagUrl', function (tag: string) {
    return `/tags/${encodeURIComponent(tag.toLowerCase().replace(/\s+/g, '-'))}/`;
  });

  Handlebars.registerHelper('isoDate', function (date: string) {
    if (!date) return '';
    return new Date(date).toISOString();
  });
}

export interface RenderContext {
  [key: string]: unknown;
  site: SiteConfig;
  posts?: Record<string, unknown>[];
  post?: Post;
  tag?: string;
  body?: string;
  title?: string;
  content?: string;
  date?: string;
  tags?: string[];
  url?: string;
  description?: string;
}

export function renderPage(
  templates: Map<string, CompiledTemplate>,
  layout: CompiledTemplate | null,
  templateName: string,
  context: RenderContext,
): string {
  const tpl = templates.get(templateName);
  if (!tpl) {
    throw new Error(`Template "${templateName}" not found`);
  }

  const pageHtml = tpl(context);

  if (layout && templateName !== 'rss') {
    return layout({ ...context, body: pageHtml });
  }

  return pageHtml;
}
