import fs from 'node:fs/promises';
import path from 'node:path';
import { hashContent } from '../hash';
import type { Page } from '../generator';
import type { BuildContext, Plugin } from '../plugin';

type Values = Record<string, unknown>;
function escapeHtml(value: string): string { return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]!)); }
function value(context: Values, key: string): unknown { return key.split('.').reduce<unknown>((current, part) => current && typeof current === 'object' ? (current as Values)[part] : undefined, context); }
function defaultLayout(title: string, body: string): string { return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`; }

async function files(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const result: string[] = [];
    for (const entry of entries) { const full = path.join(directory, entry.name); if (entry.isDirectory()) result.push(...await files(full)); else if (/\.(?:hbs|ejs)$/i.test(entry.name)) result.push(full); }
    return result;
  } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []; throw error; }
}

export class TemplatePlugin implements Plugin {
  name = 'templates';
  private renderPage!: (page: Page, body: string) => string;

  async beforeBuild(context: BuildContext): Promise<void> {
    const templates = new Map<string, { source: string; extension: string }>();
    const partials = new Map<string, string>();
    const fingerprintParts: string[] = [];
    for (const file of await files(context.templatesDir)) {
      const relative = path.relative(context.templatesDir, file).split(path.sep).join('/');
      const name = relative.replace(/\.(?:hbs|ejs)$/i, '');
      const source = await fs.readFile(file, 'utf8');
      fingerprintParts.push(`${relative}:${hashContent(source)}`);
      if (name.startsWith('partials/')) partials.set(name.slice(9), source); else templates.set(name, { source, extension: path.extname(file) });
    }
    const templateHash = hashContent(fingerprintParts.sort().join('\n'));
    if (context.build) {
      context.build.templateHash = templateHash;
      await Promise.all(context.pages.map(async (page) => {
        const cached = context.build!.cache.pages[page.source];
        if (!context.build!.incremental || context.build!.clean || !cached || cached.sourceHash !== context.build!.sourceHashes.get(page.source) || cached.templateHash !== templateHash) return;
        try {
          await fs.access(path.join(context.outputDir, `${page.slug}.html`));
          context.build!.skippedSources.add(page.source);
          context.build!.timeSavedMs += cached.buildTimeMs;
        } catch { /* Missing output must be rebuilt. */ }
      }));
    }
    const render = (source: string, context: Values, extension: string): string => extension === '.ejs' ? renderEjs(source, context, partials) : renderHandlebars(source, context, partials);
    const find = (name: string, directory = '') => templates.get(`${directory}${name.replace(/^\.?\//, '').replace(/\.(?:hbs|ejs)$/i, '')}`);
    this.renderPage = (page, body) => {
      const context: Values = { ...page, body, content: page.html };
      const selected = page.template ? find(page.template) : find('default');
      let rendered = selected ? render(selected.source, context, selected.extension) : body;
      const layoutName = page.layout === undefined ? 'default' : page.layout;
      if (layoutName !== 'false') { const layout = find(String(layoutName), 'layouts/'); if (layout) rendered = render(layout.source, { ...context, body: rendered, content: rendered }, layout.extension); else if (!selected) rendered = defaultLayout(page.title, rendered); }
      return rendered;
    };
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await fs.mkdir(context.outputDir, { recursive: true });
    const renderPages = context.pages.filter((page) => !context.build?.skippedSources.has(page.source));
    await Promise.all(renderPages.map(async (page) => {
      const started = performance.now();
      const body = `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.html}\n</main>`;
      await fs.writeFile(path.join(context.outputDir, `${page.slug}.html`), this.renderPage(page, body));
      context.build?.builtSources.add(page.source);
      context.build?.pageTimes.set(page.source, performance.now() - started);
    }));
    const links = context.pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
    const index: Page = { slug: 'index', source: 'index.md', title: 'Home', tags: [], html: '', template: undefined };
    await fs.writeFile(path.join(context.outputDir, 'index.html'), this.renderPage(index, `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  }
}

function renderHandlebars(source: string, context: Values, partials: Map<string, string>): string {
  const render = (input: string, local: Values): string => {
    let result = input.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_m, key: string, body: string) => { const items = value(local, key.trim()); return Array.isArray(items) ? items.map((item, index) => render(body, { ...local, this: item, '@index': index })).join('') : ''; });
    result = result.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_m, key: string, body: string) => value(local, key.trim()) ? render(body, local) : '');
    result = result.replace(/{{>\s*([\w./-]+)\s*}}/g, (_m, name: string) => render(partials.get(name.replace(/^partials\//, '')) ?? partials.get(`${name}.hbs`) ?? '', local));
    result = result.replace(/{{{\s*([^}]+)\s*}}}/g, (_m, key: string) => String(value(local, key.trim()) ?? ''));
    return result.replace(/{{\s*([^}]+)\s*}}/g, (_m, key: string) => escapeHtml(String(value(local, key.trim()) ?? '')));
  };
  return render(source, context);
}

function renderEjs(source: string, context: Values, partials: Map<string, string>): string {
  const include = (name: string) => { const normalized = name.replace(/^\.\//, '').replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, ''); return partials.get(normalized) ?? partials.get(name) ?? ''; };
  const evaluate = (expression: string) => value(context, expression.trim()) ?? (expression.trim() === 'this' ? context.this : undefined);
  let result = source.replace(/<%[-=]\s*include\(['"]([^'"]+)['"]\)\s*%>/g, (_m, name: string) => renderEjs(include(name), context, partials));
  result = result.replace(/<%-\s*([^%]+?)\s*%>/g, (_m, expression: string) => String(evaluate(expression) ?? ''));
  return result.replace(/<%=\s*([^%]+?)\s*%>/g, (_m, expression: string) => escapeHtml(String(evaluate(expression) ?? '')));
}
