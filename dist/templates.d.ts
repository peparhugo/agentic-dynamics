export interface PageData {
    title: string;
    date: string;
    tags: string[];
    content: string;
    slug: string;
    layout?: string;
    template?: string;
}
export declare class TemplateEngine {
    private templatesDir;
    private layoutsDir;
    private partialsDir;
    private compiledLayouts;
    private compiledTemplates;
    initialized: boolean;
    constructor(templatesDir: string);
    private loadPartials;
    private loadLayouts;
    private loadTemplates;
    private getLayout;
    private getTemplate;
    render(data: PageData): string | null;
    renderIndex(pages: PageData[]): string | null;
}
//# sourceMappingURL=templates.d.ts.map