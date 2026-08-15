export declare class TemplateEngine {
    private templatesDir;
    private layoutsDir;
    private partialsDir;
    private cache;
    constructor(templatesDir: string);
    private registerPartials;
    private getTemplate;
    renderTemplate(templatePath: string, data: Record<string, unknown>): string;
    renderLayout(layoutName: string, data: Record<string, unknown>): string;
    renderPageTemplate(templateName: string, data: Record<string, unknown>, layoutName?: string): string;
    getDefaultLayoutPath(): string;
    hasLayout(layoutName: string): boolean;
    getAvailableTemplates(): string[];
    getAvailableLayouts(): string[];
}
//# sourceMappingURL=template-engine.d.ts.map
