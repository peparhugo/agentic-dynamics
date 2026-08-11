import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

function htmlEncode(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function wrapPage(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${htmlEncode(title)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }
    a { color: #2563eb; }
    nav { margin-bottom: 2rem; }
    .meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .tag { background: #e5e7eb; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  ${body}
</body>
</html>`;
}

function renderPageHtml(page: Page): string {
  const { title, date, tags } = page.frontmatter;
  const metaParts: string[] = [];
  if (date) metaParts.push(`<time>${htmlEncode(date)}</time>`);
  const meta = metaParts.length
    ? `<div class="meta">${metaParts.join(' &middot; ')}</div>`
    : '';

  const tagsHtml =
    tags && tags.length > 0
      ? `<div class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join('\n')}</div>`
      : '';

  const body = `<article>
  <h1>${htmlEncode(title)}</h1>
  ${meta}
  ${tagsHtml}
  ${page.html}
</article>`;

  return wrapPage(title, body);
}

function renderIndexHtml(pages: Page[]): string {
  const items = pages
    .map((p) => {
      const { title, date, tags } = p.frontmatter;
      const tagsHtml =
        tags && tags.length > 0
          ? ` <span class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join(' ')}</span>`
          : '';
      const dateHtml = date ? ` <time>${htmlEncode(date)}</time>` : '';
      return `<li>
      <a href="${htmlEncode(p.slug)}.html">${htmlEncode(title)}</a>${dateHtml}${tagsHtml}
    </li>`;
    })
    .join('\n');

  const body = `<h1>All Posts</h1>
  <ul>
    ${items}
  </ul>`;

  return wrapPage('Index', body);
}

interface TemplateEngine {
  renderPage(page: Page): string;
  renderIndex(pages: Page[]): string;
}

function registerPartials(partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) return;
  const files = fs.readdirSync(partialsDir).filter((f) => f.endsWith('.hbs'));
  for (const file of files) {
    const name = path.basename(file, '.hbs');
    const content = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
    Handlebars.registerPartial(name, content);
  }
}

function loadTemplates(templateDir: string): TemplateEngine | null {
  if (!fs.existsSync(templateDir)) return null;

  const partialsDir = path.join(templateDir, 'partials');
  registerPartials(partialsDir);

  const layoutsDir = path.join(templateDir, 'layouts');
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  if (fs.existsSync(layoutsDir)) {
    const files = fs.readdirSync(layoutsDir).filter((f) => f.endsWith('.hbs'));
    for (const file of files) {
      const name = path.basename(file, '.hbs');
      const content = fs.readFileSync(path.join(layoutsDir, file), 'utf-8');
      layouts.set(name, Handlebars.compile(content));
    }
  }

  const pageTemplates = new Map<string, Handlebars.TemplateDelegate>();
  const files = fs.readdirSync(templateDir).filter((f) => f.endsWith('.hbs'));
  for (const file of files) {
    const name = path.basename(file, '.hbs');
    const content = fs.readFileSync(path.join(templateDir, file), 'utf-8');
    pageTemplates.set(name, Handlebars.compile(content));
  }

  return {
    renderPage(page: Page): string {
      const templateName = page.frontmatter.template || 'page';
      const template =
        pageTemplates.get(templateName) || pageTemplates.get('page');
      if (!template) {
        throw new Error(`Page template "${templateName}" not found`);
      }

      const layoutName = page.frontmatter.layout || 'default';
      const layout =
        layouts.get(layoutName) || layouts.get('default');

      const body = template({
        title: page.frontmatter.title,
        date: page.frontmatter.date,
        tags: page.frontmatter.tags || [],
        content: page.html,
        slug: page.slug,
      });

      if (layout) {
        return layout({
          title: page.frontmatter.title,
          body,
        });
      }

      return body;
    },

    renderIndex(pages: Page[]): string {
      const hasIndex = pageTemplates.has('index');
      if (!hasIndex) {
        return renderIndexHtml(pages);
      }

      const template = pageTemplates.get('index')!;
      const layout = layouts.get('default');

      const body = template({
        pages: pages.map((p) => ({
          title: p.frontmatter.title,
          date: p.frontmatter.date,
          tags: p.frontmatter.tags || [],
          slug: p.slug,
        })),
      });

      if (layout) {
        return layout({ title: 'Index', body });
      }

      return body;
    },
  };
}

export function generateSite(
  pages: Page[],
  outputDir: string,
  templateDir?: string
): void {
  const engine = templateDir ? loadTemplates(templateDir) : null;

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = engine ? engine.renderPage(page) : renderPageHtml(page);
    fs.writeFileSync(
      path.join(outputDir, `${page.slug}.html`),
      html,
      'utf-8'
    );
  }

  const indexHtml = engine ? engine.renderIndex(pages) : renderIndexHtml(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');
}
