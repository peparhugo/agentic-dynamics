import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext } from '../plugin';
import { Page, PageTemplateData } from '../types';
import { TemplateEngine } from '../template-engine';

function toTemplateData(page: Page): PageTemplateData {
  const { title, date, tags } = page.frontmatter;
  return {
    title,
    date,
    dateFormatted: date ? new Date(date).toLocaleDateString('en-US') : undefined,
    tags,
    tagsStr: tags && tags.length > 0 ? tags.join(', ') : undefined,
    content: page.html,
    slug: page.slug,
  };
}

export class TemplatePlugin implements Plugin {
  name = 'template';
  private engine: TemplateEngine | null = null;

  onStart(context: BuildContext): void {
    const { templateDir } = context.options;
    this.engine = new TemplateEngine(templateDir);
  }

  onFile(page: Page, context: BuildContext): void {
    if (!this.engine) return;

    const data = toTemplateData(page);
    const pageHTML = this.engine.renderPage(data, page.frontmatter.template, page.frontmatter.layout);
    const outPath = path.join(context.outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, pageHTML, 'utf-8');
  }

  afterBuild(context: BuildContext): void {
    if (!this.engine) return;

    const indexData = {
      title: 'My Static Site',
      pages: context.pages.map(toTemplateData),
    };
    const indexHTML = this.engine.renderIndex(indexData);
    fs.writeFileSync(path.join(context.outputDir, 'index.html'), indexHTML, 'utf-8');
  }
}
