import { Page, Plugin } from '../plugin';
/**
 * Built-in plugin that renders each page through a Handlebars template.
 *
 * It prefers the layout named by the page's `template` metadata, falling back
 * to the `default` layout, and finally to the built-in HTML page renderer when
 * no layout matches. The final full-page HTML is stored in `page.rendered`.
 */
export declare class TemplatePlugin implements Plugin {
    name: string;
    private engine;
    constructor(templatesDir: string);
    onFile(page: Page): void;
}
