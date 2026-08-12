import fs from 'fs';
import path from 'path';
import { Page } from './types';
import { parseMarkdown, slugify } from './markdown';
import {
  DEFAULT_TEMPLATES_DIR,
  DEFAULT_PAGE_TEMPLATE_NAME,
  DEFAULT_LAYOUT_NAME,
  TemplateEngine,
  pageToContext,
} from './template';

const MARKDOWN_RE = /\.(md|markdown)$/i;

export interface BuildSiteOptions {
  templatesDir?: string;
}

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  const results: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && MARKDOWN_RE.test(entry.name)) {
        results.push(full);
      }
    }
  };
  walk(contentDir);
  return results.sort();
}

export function readPages(contentDir: string): Page[] {
  return collectMarkdownFiles(contentDir).map((filePath) => {
    const slug = slugify(path.basename(filePath));
    const raw = fs.readFileSync(filePath, 'utf8');
    const doc = parseMarkdown(slug, raw);
    return {
      slug: doc.slug,
      title: doc.title,
      date: doc.date,
      tags: doc.tags,
      template: doc.template,
      layout: doc.layout,
      data: doc.data,
      content: doc.content,
    };
  });
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.date ? Date.parse(a.date) : -Infinity;
    const db = b.date ? Date.parse(b.date) : -Infinity;
    if (da !== db) {
      return db - da;
    }
    return a.title.localeCompare(b.title);
  });
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPageBody(page: Page): string {
  const dateTag = page.date
    ? `    <p class="date"><time datetime="${escapeHtml(page.date)}">${escapeHtml(
        page.date,
      )}</time></p>\n`
    : '';
  const tags = page.tags.length
    ? `    <p class="tags">${page.tags
        .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
        .join(' ')}</p>\n`
    : '';
  return `  <article>
    <h1>${escapeHtml(page.title)}</h1>
${dateTag}${tags}    ${page.content}
  </article>`;
}

export function renderPage(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
${renderPageBody(page)}
  <p><a href="index.html">&larr; Back to index</a></p>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((p) => {
      const date = p.date ? ` <time>${escapeHtml(p.date)}</time>` : '';
      const tags = p.tags.length
        ? ` <span class="tags">${p.tags
            .map((t) => `#${escapeHtml(t)}`)
            .join(' ')}</span>`
        : '';
      return `    <li><a href="${encodeURIComponent(p.slug)}.html">${escapeHtml(
        p.title,
      )}</a>${date}${tags}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</body>
</html>
`;
}

export function renderPageWithEngine(page: Page, engine: TemplateEngine): string {
  const name = page.template ?? DEFAULT_PAGE_TEMPLATE_NAME;
  const template = engine.getPageTemplate(name);
  let bodyHtml: string;
  if (template) {
    bodyHtml = engine.render(template.source, template.ext, pageToContext(page));
  } else {
    bodyHtml = renderPageBody(page);
  }

  const layoutName = page.layout ?? DEFAULT_LAYOUT_NAME;
  const layout = engine.getLayout(layoutName);
  if (layout) {
    return engine.render(
      layout.source,
      layout.ext,
      pageToContext(page, bodyHtml),
    );
  }
  return bodyHtml;
}

export function renderIndexWithEngine(pages: Page[], engine: TemplateEngine): string {
  const indexTemplate = engine.getIndexTemplate();
  if (indexTemplate) {
    return engine.render(
      indexTemplate.source,
      indexTemplate.ext,
      {
        page: {},
        title: 'Index',
        date: undefined,
        tags: [],
        content: '',
        pages,
        site: { pages },
      },
    );
  }
  return renderIndex(pages);
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  options: BuildSiteOptions | string = {},
): Page[] {
  const opts: BuildSiteOptions =
    typeof options === 'string' ? { templatesDir: options } : options;
  const pages = sortPages(readPages(contentDir));
  const templatesDir = opts.templatesDir ?? DEFAULT_TEMPLATES_DIR;
  const engine = new TemplateEngine(templatesDir);

  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(
    path.join(outputDir, 'index.html'),
    engine.enabled ? renderIndexWithEngine(pages, engine) : renderIndex(pages),
    'utf8',
  );
  for (const page of pages) {
    fs.writeFileSync(
      path.join(outputDir, `${page.slug}.html`),
      engine.enabled ? renderPageWithEngine(page, engine) : renderPage(page),
      'utf8',
    );
  }
  return pages;
}
