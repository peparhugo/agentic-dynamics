import { Plugin, SsgContext } from '../plugin';
import { Page } from '../types';
import { renderPageHtml } from '../core';
import {
  registerPartials,
  renderPageWithTemplates,
  templateDirExists,
} from '../template';

export class TemplatePlugin implements Plugin {
  name = 'template';

  async beforeBuild(ctx: SsgContext): Promise<void> {
    const templateDir = ctx.templateDir;
    if (await templateDirExists(templateDir)) {
      await registerPartials(templateDir);
    }
  }

  async onFile(page: Page, ctx: SsgContext): Promise<Page> {
    const templateDir = ctx.templateDir;
    const useTemplates = await templateDirExists(templateDir);
    page.renderedHtml = useTemplates
      ? await renderPageWithTemplates(page, templateDir)
      : renderPageHtml(page);
    return page;
  }
}
