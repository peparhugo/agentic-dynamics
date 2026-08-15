export type TemplateContext = Record<string, unknown>;
export declare class TemplateEngine {
    private readonly root;
    private readonly hbs;
    private readonly pageTemplates;
    private readonly layouts;
    private readonly defaultPageTemplate;
    private readonly defaultLayout;
    constructor(root: string);
    load(): Promise<void>;
    private loadPartials;
    private loadLayouts;
    private loadPageTemplates;
    render(name: string, context: TemplateContext): string;
    renderLayout(name: string, context: TemplateContext): string;
}
