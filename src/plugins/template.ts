import { Plugin, Page, BuildOptions } from '../plugin';
import { TemplateEngine, PageData } from '../templates';

export function renderPage(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.title}</title>
${page.tags.length ? `  <meta name="keywords" content="${page.tags.join(', ')}">` : ''}
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${page.title}</h1>
${page.date ? `      <time>${page.date}</time>` : ''}
      <div>${page.content}</div>
    </article>
  </main>
</body>
</html>`;
}

export function renderIndex(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const dateStr = page.date ? ` <time>${page.date}</time>` : '';
      const tagsStr = page.tags.length ? ` [${page.tags.join(', ')}]` : '';
      return `      <li><a href="${page.slug}.html">${page.title}</a>${dateStr}${tagsStr}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Pages</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
${listItems}
    </ul>
  </main>
</body>
</html>`;
}

export class TemplatePlugin implements Plugin {
  name = 'template';
  private engine: TemplateEngine | null = null;
  private templatesDir?: string;

  beforeBuild(options: BuildOptions): void {
    this.templatesDir = options.templatesDir;
    this.engine = options.templatesDir ? new TemplateEngine(options.templatesDir) : null;
  }

  onFile(page: Page): Page {
    return page;
  }

  render(page: Page): string | null {
    if (!this.engine || !this.engine.initialized) return null;
    return this.engine.render(page as PageData);
  }

  renderIndex(pages: Page[]): string | null {
    if (!this.engine || !this.engine.initialized) return null;
    return this.engine.renderIndex(pages as PageData[]);
  }
}
