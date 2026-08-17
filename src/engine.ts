import { promises as fs } from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import type { Page } from './types';

const STYLE = [
  'body { font-family: system-ui, -apple-system, sans-serif; max-width: 48rem; margin: 0 auto; padding: 1.5rem; line-height: 1.6; color: #1a1a1a; }',
  'header { margin-bottom: 2rem; }',
  'a { color: #0b5fff; text-decoration: none; }',
  'a:hover { text-decoration: underline; }',
  '.meta { display: flex; gap: 1rem; align-items: center; color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }',
  '.tags { display: flex; gap: 0.5rem; }',
  '.tag { background: #eef2ff; color: #3b4fd8; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; }',
  '.content h1 { font-size: 1.6rem; }',
].join('\n');

const BUILTIN_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<style>
${STYLE}
</style>
</head>
<body>
<header><a href="index.html">&larr; Home</a></header>
<main>
{{{body}}}
</main>
</body>
</html>
`;

const BUILTIN_PAGE_TEMPLATE = `<article>
<h1>{{title}}</h1>
{{#if date}}<div class="meta"><time datetime="{{date}}">{{date}}</time>{{#if tags.length}}<div class="tags">{{#each tags}}<span class="tag">{{this}}</span>{{/each}}</div>{{/if}}</div>{{/if}}
{{#if tags.length}}{{#unless date}}<div class="meta"><div class="tags">{{#each tags}}<span class="tag">{{this}}</span>{{/each}}</div></div>{{/unless}}{{/if}}
<div class="content">
{{{content}}}
</div>
</article>
`;

const BUILTIN_INDEX_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Index</title>
<style>
${STYLE}
</style>
</head>
<body>
<header><h1>Index</h1></header>
<main>
<ul>
{{#each pages}}
<li><a href="{{slug}}.html">{{title}}</a>{{#if date}} <time>{{date}}</time>{{/if}}{{#if tags.length}}<div class="tags">{{#each tags}}<span class="tag">{{this}}</span>{{/each}}</div>{{/if}}</li>
{{/each}}
</ul>
</main>
</body>
</html>
`;

export const BUILTIN_TEMPLATE_SOURCE = `${BUILTIN_LAYOUT}\n${BUILTIN_PAGE_TEMPLATE}\n${BUILTIN_INDEX_TEMPLATE}`;

export interface PageContext {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  content: string;
  body: string;
  [key: string]: unknown;
}

export interface TemplateEngine {
  renderPage(page: Page): string;
  renderIndex(pages: Page[]): string;
}

function toContext(page: Page): PageContext {
  return {
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    content: page.html,
    body: page.html,
  };
}

async function listTemplateFiles(dir: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    return entries
      .filter((e) => e.isFile() && e.name.toLowerCase().endsWith('.hbs'))
      .map((e) => path.join(dir, e.name));
  } catch {
    return [];
  }
}

async function loadTemplates(
  hbs: typeof Handlebars,
  dir: string
): Promise<Map<string, Handlebars.TemplateDelegate>> {
  const map = new Map<string, Handlebars.TemplateDelegate>();
  for (const file of await listTemplateFiles(dir)) {
    const name = path.basename(file, path.extname(file));
    const source = await fs.readFile(file, 'utf8');
    map.set(name, hbs.compile(source));
  }
  return map;
}

export async function createTemplateEngine(
  templatesDir: string
): Promise<TemplateEngine> {
  const hbs = Handlebars.create();

  const partialsDir = path.join(templatesDir, 'partials');
  for (const file of await listTemplateFiles(partialsDir)) {
    const name = path.basename(file, path.extname(file));
    const source = await fs.readFile(file, 'utf8');
    hbs.registerPartial(name, hbs.compile(source));
  }

  const layouts = await loadTemplates(hbs, path.join(templatesDir, 'layouts'));
  const pageTemplates = await loadTemplates(hbs, templatesDir);

  let indexTemplate: Handlebars.TemplateDelegate | undefined;
  try {
    const source = await fs.readFile(path.join(templatesDir, 'index.hbs'), 'utf8');
    indexTemplate = hbs.compile(source);
  } catch {
    indexTemplate = undefined;
  }

  const defaultLayout = hbs.compile(BUILTIN_LAYOUT);
  const defaultPageTemplate = hbs.compile(BUILTIN_PAGE_TEMPLATE);
  const defaultIndexTemplate = hbs.compile(BUILTIN_INDEX_TEMPLATE);

  return {
    renderPage(page: Page): string {
      const context = toContext(page);
      const templateName = page.template ?? 'default';
      const layoutName = page.layout ?? 'default';

      const pageTemplate = pageTemplates.get(templateName) ?? defaultPageTemplate;
      const body = pageTemplate({ ...context });

      const layout = layouts.get(layoutName) ?? defaultLayout;
      return layout({ ...context, body });
    },
    renderIndex(pages: Page[]): string {
      const template = indexTemplate ?? defaultIndexTemplate;
      return template({ pages });
    },
  };
}
