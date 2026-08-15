import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export interface TemplateData {
  title: string;
  date?: string;
  tags?: string[];
  slug: string;
  body: string;
  [key: string]: unknown;
}

export interface TemplateEngine {
  renderPage(templateName: string, data: TemplateData): string;
  renderLayout(layoutName: string, data: TemplateData): string;
}

function ensureDirectoryExists(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function loadPartials(partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) {
    return;
  }

  const files = fs.readdirSync(partialsDir);
  for (const file of files) {
    if (file.endsWith('.hbs') || file.endsWith('.html')) {
      const partialName = file.replace(/\.(hbs|html)$/, '');
      const partialPath = path.join(partialsDir, file);
      const partialContent = fs.readFileSync(partialPath, 'utf-8');
      Handlebars.registerPartial(partialName, partialContent);
    }
  }
}

function getTemplate(templatePath: string, defaultTemplate: string): string {
  if (fs.existsSync(templatePath)) {
    return fs.readFileSync(templatePath, 'utf-8');
  }
  const htmlPath = templatePath.replace(/\.hbs$/, '.html');
  if (htmlPath !== templatePath && fs.existsSync(htmlPath)) {
    return fs.readFileSync(htmlPath, 'utf-8');
  }
  return defaultTemplate;
}

export function createTemplateEngine(templatesDir: string): TemplateEngine {
  ensureDirectoryExists(templatesDir);
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');

  ensureDirectoryExists(layoutsDir);
  ensureDirectoryExists(partialsDir);

  const defaultLayoutTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  <header>
    <a href="/index.html">← Home</a>
  </header>
  {{{body}}}
</body>
</html>`;

  const defaultPageTemplate = `<article>
  <h1>{{title}}</h1>
  {{#if date}}<p class="date">{{date}}</p>{{/if}}
  {{#if tags}}<p class="tags">Tags: {{#each tags}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}</p>{{/if}}
  {{{body}}}
</article>`;

  const defaultIndexTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <header>
    <h1>Welcome</h1>
  </header>
  <main>
    <ul>
      {{#each pages}}<li><a href="{{this.slug}}.html">{{this.title}}</a>{{#if this.date}} ({{this.date}}){{/if}}</li>
      {{/each}}
    </ul>
  </main>
</body>
</html>`;

  return {
    renderPage(templateName: string, data: TemplateData): string {
      loadPartials(partialsDir);
      const templatePath = path.join(templatesDir, `${templateName}.hbs`);
      const templateContent = getTemplate(templatePath, defaultPageTemplate);
      const template = Handlebars.compile(templateContent);
      return template(data);
    },

    renderLayout(layoutName: string, data: TemplateData): string {
      loadPartials(partialsDir);
      const layoutPath = path.join(layoutsDir, `${layoutName}.hbs`);
      const layoutContent = getTemplate(layoutPath, defaultLayoutTemplate);
      const template = Handlebars.compile(layoutContent);
      return template(data);
    },
  };
}

export function renderIndexWithTemplate(templatesDir: string, pages: TemplateData[]): string {
  const partialsDir = path.join(templatesDir, 'partials');
  const layoutsDir = path.join(templatesDir, 'layouts');
  loadPartials(partialsDir);
  const indexLayoutPath = path.join(layoutsDir, 'index.hbs');

  const defaultIndexTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <header>
    <h1>Welcome</h1>
  </header>
  <main>
    <ul>
      {{#each pages}}<li><a href="{{this.slug}}.html">{{this.title}}</a>{{#if this.date}} ({{this.date}}){{/if}}</li>
      {{/each}}
    </ul>
  </main>
</body>
</html>`;

  const layoutContent = fs.existsSync(indexLayoutPath)
    ? fs.readFileSync(indexLayoutPath, 'utf-8')
    : defaultIndexTemplate;

  const template = Handlebars.compile(layoutContent);
  return template({ pages });
}

export function renderEmptyIndex(templatesDir: string): string {
  const partialsDir = path.join(templatesDir, 'partials');
  const layoutsDir = path.join(templatesDir, 'layouts');
  loadPartials(partialsDir);
  const indexLayoutPath = path.join(layoutsDir, 'index.hbs');

  const defaultEmptyTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <h1>Welcome</h1>
  <p>No pages found.</p>
</body>
</html>`;

  const layoutContent = fs.existsSync(indexLayoutPath)
    ? fs.readFileSync(indexLayoutPath, 'utf-8')
    : defaultEmptyTemplate;

  const template = Handlebars.compile(layoutContent);
  return template({});
}
