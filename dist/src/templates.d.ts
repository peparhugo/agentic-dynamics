import Handlebars from 'handlebars';
import { Page } from './types';
export interface TemplateBundle {
    exists: boolean;
    hbs: typeof Handlebars;
    templates: Map<string, Handlebars.TemplateDelegate>;
    layouts: Map<string, Handlebars.TemplateDelegate>;
    partials: Map<string, Handlebars.TemplateDelegate>;
    templatesSource: Map<string, string>;
    layoutsSource: Map<string, string>;
    partialsSource: Map<string, string>;
    defaultTemplate: string | null;
    defaultLayout: string | null;
    hasIndexTemplate: boolean;
}
/**
 * Load the template tree at `templatesDir`.
 *
 * Expected layout:
 *   ./templates/            page templates (.hbs)
 *   ./templates/layouts/    layout templates (.hbs)
 *   ./templates/partials/   reusable partials (.hbs)
 *
 * `default.hbs` is used when a page does not name a template and
 * `layouts/default.hbs` wraps every rendered page unless the page opts out
 * via a `layout:` frontmatter field.
 */
export declare function loadTemplates(templatesDir: string): Promise<TemplateBundle>;
/**
 * Render a single page through its template and layout. Throws when a page
 * explicitly names a template or layout that cannot be found.
 */
export declare function renderPageTemplate(page: Page, bundle: TemplateBundle): string;
/**
 * Render the site index from `index.hbs` when present, otherwise return null
 * so callers can fall back to the built-in index renderer.
 */
export declare function renderIndexTemplate(pages: Page[], bundle: TemplateBundle): string | null;
/**
 * Fingerprint of the templates a page renders through: its page template, its
 * layout, and every registered partial (partials are global). When no template
 * directory is configured the page output depends only on its source, so the
 * hash is empty.
 */
export declare function computePageTemplateHash(page: Page, bundle: TemplateBundle): string;
