import type { Page } from './types';
import {
  DEFAULT_LAYOUT,
  DEFAULT_TEMPLATE,
  renderTemplateFile,
  TemplateSet,
} from './templates';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function pageContext(page: Page): Record<string, unknown> {
  return {
    ...page.data,
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    html: page.html,
    markdown: page.markdown,
  };
}

export function renderPageWithTemplates(page: Page, templates: TemplateSet): string {
  const templateName = page.template ?? DEFAULT_TEMPLATE;
  if (page.template !== undefined && !templates.templates.has(templateName)) {
    throw new Error(`Template not found: ${templateName}`);
  }

  const template = templates.templates.get(templateName);
  if (!template) return renderPage(page);

  const partials = [...templates.partials.values()];
  const content = renderTemplateFile(template, pageContext(page), partials);

  const layoutName = page.layout ?? DEFAULT_LAYOUT;
  if (page.layout !== undefined && !templates.layouts.has(layoutName)) {
    throw new Error(`Layout not found: ${layoutName}`);
  }

  const layout = templates.layouts.get(layoutName);
  if (!layout) return content;

  const context = { ...pageContext(page), body: content };
  return renderTemplateFile(layout, context, partials);
}

export function renderIndexWithTemplates(pages: Page[], templates: TemplateSet): string {
  const template = templates.templates.get('index');
  if (!template) return renderIndex(pages);

  const partials = [...templates.partials.values()];
  const context: Record<string, unknown> = { pages: pages.map(pageContext) };
  const content = renderTemplateFile(template, context, partials);

  const layout = templates.layouts.get(DEFAULT_LAYOUT);
  if (!layout) return content;

  return renderTemplateFile(layout, { ...context, body: content }, partials);
}

export function renderPage(page: Page): string {
  const title = escapeHtml(page.title);
  const tagLine = page.tags.length > 0
    ? `<p class="tags">Tags: ${page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ')}</p>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
</head>
<body>
<article>
<h1>${title}</h1>
${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}
${tagLine}
${page.html}
</article>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const date = page.date ? ` &mdash; <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
      return `  <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${date}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home</title>
</head>
<body>
<main>
<h1>Pages</h1>
<ul>
${listItems}
</ul>
</main>
</body>
</html>
`;
}
