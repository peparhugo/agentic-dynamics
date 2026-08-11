import { Plugin, Page, BuildOptions } from '../plugin';
export declare function renderPage(page: Page): string;
export declare function renderIndex(pages: Page[]): string;
export declare class TemplatePlugin implements Plugin {
    name: string;
    private engine;
    private templatesDir?;
    beforeBuild(options: BuildOptions): void;
    onFile(page: Page): Page;
    render(page: Page): string | null;
    renderIndex(pages: Page[]): string | null;
}
//# sourceMappingURL=template.d.ts.map