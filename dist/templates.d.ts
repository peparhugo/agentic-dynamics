import { Page } from './types';
export declare class TemplateEngine {
    private templatesDir;
    private compiled;
    private builtins;
    constructor(templatesDir: string);
    private loadPartials;
    private loadFromDisk;
    private getTemplate;
    renderPage(page: Page): string;
    renderIndex(pages: Page[]): string;
    renderLayout(title: string, body: string, layoutName?: string): string;
}
//# sourceMappingURL=templates.d.ts.map