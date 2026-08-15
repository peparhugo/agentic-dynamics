export interface TemplateEngine {
    registerPartial(name: string, content: string): void;
    render(templateContent: string, data: Record<string, unknown>): string;
}
export declare function setTemplateDir(dir: string): void;
export declare function setDefaultLayout(name: string): void;
export declare function createTemplateEngine(): TemplateEngine;
export declare function getEngine(): TemplateEngine;
export declare function loadPartials(templateDir: string): Promise<void>;
export declare function loadTemplate(templateName: string, templateDir: string): Promise<string>;
export declare function loadLayout(layoutName: string, templateDir: string): Promise<string>;
export declare function renderPage(pageHtml: string, templateContent: string | null, layoutName: string | null, pageData: Record<string, unknown>, templateDir: string): Promise<string>;
//# sourceMappingURL=template.d.ts.map