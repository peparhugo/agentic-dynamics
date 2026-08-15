import { parseMarkdown } from './markdown';
import { renderTemplatePage } from './template';
import { Plugin } from './types';

/** Converts source markdown into page metadata and HTML. */
export const MarkdownPlugin: Plugin = {
  onFile(page) {
    const fallbackTitle = page.sourceFile.replace(/^.*[\\/]/, '').replace(/\.md$/i, '');
    const parsed = parseMarkdown(page.source, fallbackTitle);
    page.metadata = parsed.metadata;
    page.html = parsed.html;
  },
};

/** Applies the selected Handlebars page template and layout. */
export const TemplatePlugin: Plugin = {
  async onFile(page, context) {
    page.renderedHtml = await renderTemplatePage(page.metadata, page.html, context.templatesDirectory);
  },
};
