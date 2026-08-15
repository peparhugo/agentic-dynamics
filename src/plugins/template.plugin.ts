import { Plugin, PluginContext } from '../plugin';
import { PageData } from '../page';
import { loadPartials, loadTemplate, loadLayout, getEngine } from '../template';

export const TemplatePlugin: Plugin = {
  name: 'template',

  beforeBuild: async (context: PluginContext): Promise<void> => {
    if (context.templateDir) {
      await loadPartials(context.templateDir);
    }
  },

  onFile: async (page: PageData, context: PluginContext): Promise<PageData> => {
    if (!context.templateDir) {
      return page;
    }

    const eng = getEngine();
    let html = page.html;

    if (page.template) {
      const templateContent = await loadTemplate(page.template, context.templateDir);
      html = eng.render(templateContent, { ...page, body: page.html });
    }

    if (page.layout) {
      const layout = await loadLayout(page.layout, context.templateDir);
      html = eng.render(layout, { ...page, body: html });
    }

    return {
      ...page,
      html
    };
  }
};
