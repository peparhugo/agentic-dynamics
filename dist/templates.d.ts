import { PageData } from './types';
export interface TemplateConfig {
    templatesDir: string;
}
export declare class TemplateEngine {
    private templatesDir;
    private pageTemplates;
    private layouts;
    private initialized;
    constructor(config: TemplateConfig);
    init(): void;
    renderPage(page: PageData): string;
    renderIndex(pages: PageData[], indexLayout?: string, indexTemplate?: string): string;
}
