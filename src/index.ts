/**
 * Public API surface for the static site generator.
 */

export * from './types';
export { parseFrontmatter, parseYamlBlock, extractYamlBlock, coerceScalar, normalizeTags } from './frontmatter';
export { markdownToHtml } from './markdown';
export { escapeHtml, pageTitle, renderIndex, renderPage } from './render';
export {
  DEFAULT_TEMPLATE,
  DEFAULT_LAYOUT,
  DEFAULT_TEMPLATES_DIR,
  TEMPLATE_EXTENSION,
  hasTemplates,
  loadTemplates,
  pageContext,
  renderIndexWithTemplates,
  renderPageWithTemplates,
  renderTemplateFile,
  resolveTemplateName,
} from './templates';
export { buildSite, loadPages, listMarkdownFiles, readPage, slugify } from './site';
