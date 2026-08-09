import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import fg from 'fast-glob';

export type TemplateEnv = {
  renderLayout: (layoutName: string, context: any) => string;
  renderPageTemplate: (templateName: string, context: any) => string | null;
  hasTagTemplate: boolean;
  renderTagTemplate: (context: any) => string;
};

function registerPartials(templatesDir: string) {
  const partialsDir = path.join(templatesDir, 'partials');
  if (!fs.existsSync(partialsDir)) return;
  const files = fg.sync(['**/*.hbs'], { cwd: partialsDir, onlyFiles: true });
  for (const rel of files) {
    const partialName = rel.replace(/\\/g, '/').replace(/\.hbs$/, '');
    const full = path.join(partialsDir, rel);
    Handlebars.registerPartial(partialName, fs.readFileSync(full, 'utf8'));
  }
}

export function loadTemplates(templatesDir: string): TemplateEnv {
  registerPartials(templatesDir);

  const layoutsDir = path.join(templatesDir, 'layouts');
  const pagesDir = path.join(templatesDir, 'pages');
  let layoutsCache: Record<string, Handlebars.TemplateDelegate> = {};
  let pagesCache: Record<string, Handlebars.TemplateDelegate> = {};

  if (fs.existsSync(layoutsDir)) {
    const files = fg.sync(['**/*.hbs'], { cwd: layoutsDir, onlyFiles: true });
    for (const rel of files) {
      const key = rel.replace(/\\/g, '/').replace(/\.hbs$/, '');
      const full = path.join(layoutsDir, rel);
      layoutsCache[key] = Handlebars.compile(fs.readFileSync(full, 'utf8'));
    }
  }
  if (fs.existsSync(pagesDir)) {
    const files = fg.sync(['**/*.hbs'], { cwd: pagesDir, onlyFiles: true });
    for (const rel of files) {
      const key = rel.replace(/\\/g, '/').replace(/\.hbs$/, '');
      const full = path.join(pagesDir, rel);
      pagesCache[key] = Handlebars.compile(fs.readFileSync(full, 'utf8'));
    }
  }

  const tagTemplatePath = path.join(templatesDir, 'tag.hbs');
  const hasTagTemplate = fs.existsSync(tagTemplatePath);
  const tagTpl = hasTagTemplate
    ? Handlebars.compile(fs.readFileSync(tagTemplatePath, 'utf8'))
    : Handlebars.compile(`
      <h1>Tag: {{tag}}</h1>
      <ul>
        {{#each pages}}
          <li><a href="/{{this.urlPath}}">{{this.data.title}}</a></li>
        {{/each}}
      </ul>
    `);

  const renderLayout = (layoutName: string, context: any) => {
    const key = layoutName.endsWith('.hbs') ? layoutName.replace(/\.hbs$/, '') : layoutName;
    const tpl = layoutsCache[key] || layoutsCache[`./${key}`] || layoutsCache[`layouts/${key}`];
    if (!tpl) {
      throw new Error(`Layout not found: ${layoutName}`);
    }
    return tpl(context);
  };

  const renderPageTemplate = (templateName: string, context: any) => {
    const key = templateName.endsWith('.hbs') ? templateName.replace(/\.hbs$/, '') : templateName;
    const tpl = pagesCache[key] || pagesCache[`./${key}`] || pagesCache[`pages/${key}`];
    if (!tpl) return null;
    return tpl(context);
  };

  const renderTagTemplate = (context: any) => tagTpl(context);

  return { renderLayout, renderPageTemplate, hasTagTemplate, renderTagTemplate };
}
