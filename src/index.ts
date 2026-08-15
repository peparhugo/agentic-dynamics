/**
 * Public API surface for the static site generator.
 */

export * from './types';
export { parseFrontmatter, parseYamlBlock, extractYamlBlock, coerceScalar, normalizeTags } from './frontmatter';
export { markdownToHtml } from './markdown';
export { escapeHtml, pageTitle, renderIndex, renderPage } from './render';
export { buildSite, loadPages, listMarkdownFiles, readPage, slugify } from './site';
