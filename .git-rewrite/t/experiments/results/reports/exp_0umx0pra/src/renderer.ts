import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { SiteConfig, PageData, TemplateContext } from './types';

export function setupHandlebars(config: SiteConfig): void {
  registerPartials(config.templateDir);
  registerHelpers();
}

function registerPartials(templateDir: string): void {
  const partialsDir = path.join(templateDir, 'partials');
  if (!fs.existsSync(partialsDir)) return;

  for (const file of fs.readdirSync(partialsDir)) {
    if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
      const name = path.basename(file, path.extname(file));
      const content = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
      Handlebars.registerPartial(name, content);
    }
  }
}

function registerHelpers(): void {
  Handlebars.registerHelper('formatDate', function (date: string) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  });

  Handlebars.registerHelper('eq', function (a: unknown, b: unknown) {
    return a === b;
  });
}

const FALLBACK_TEMPLATE = `<!DOCTYPE html>
<html>
<head><title>{{page.frontmatter.title}}</title></head>
<body>{{{content}}}</body>
</html>`;

export function renderPage(
  page: PageData,
  allPages: PageData[],
  config: SiteConfig
): string {
  const context: TemplateContext = {
    page,
    pages: allPages.filter((p) => !p.isDraft || config.includeDrafts),
    site: config,
  };

  const templateName = page.frontmatter.template || 'default';
  const templatePath = path.join(config.templateDir, `${templateName}.hbs`);

  let templateContent: string;
  if (fs.existsSync(templatePath)) {
    templateContent = fs.readFileSync(templatePath, 'utf-8');
  } else if (templateName === 'default') {
    templateContent = FALLBACK_TEMPLATE;
  } else {
    throw new Error(`Template not found: ${templateName}.hbs`);
  }

  const template = Handlebars.compile(templateContent);
  let html = template({ ...context, content: page.html });

  if (page.frontmatter.layout) {
    const layoutPath = path.join(
      config.templateDir,
      'layouts',
      `${page.frontmatter.layout}.hbs`
    );
    if (fs.existsSync(layoutPath)) {
      const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
      const layoutTemplate = Handlebars.compile(layoutContent);
      html = layoutTemplate({
        ...context,
        content: page.html,
        body: html,
      });
    }
  }

  return html;
}

export function renderTagPage(
  tag: string,
  taggedPages: PageData[],
  allPages: PageData[],
  config: SiteConfig
): string {
  const templatePath = path.join(config.templateDir, 'tag.hbs');

  let templateContent: string;
  if (fs.existsSync(templatePath)) {
    templateContent = fs.readFileSync(templatePath, 'utf-8');
  } else {
    templateContent = `<!DOCTYPE html>
<html>
<head><title>Tag: {{tag}} - {{site.siteTitle}}</title></head>
<body>
  <h1>Posts tagged: {{tag}}</h1>
  <ul>
    {{#each taggedPages}}
    <li><a href="{{this.url}}">{{this.frontmatter.title}}</a></li>
    {{/each}}
  </ul>
</body>
</html>`;
  }

  const template = Handlebars.compile(templateContent);

  const context = {
    page: {
      frontmatter: { title: `Tag: ${tag}`, tags: [], draft: false },
      html: '',
      url: `/tags/${tag}/`,
      slug: `tags/${tag}`,
      tags: [] as string[],
      isDraft: false,
    } as PageData,
    pages: allPages.filter((p) => !p.isDraft || config.includeDrafts),
    taggedPages,
    tag,
    site: config,
  };

  return template(context);
}
