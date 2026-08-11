import { Page } from './types';
export interface TemplateEngineOptions {
    templatesDir: string;
}
export declare class TemplateEngine {
    private pageTemplate;
    private indexTemplate;
    private layoutTemplate;
    private customTemplates;
    private customLayouts;
    private initialized;
    constructor();
    init(templatesDir: string): void;
    renderPage(page: Page): string;
    renderIndex(pages: Page[]): string;
}
