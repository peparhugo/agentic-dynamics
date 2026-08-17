export declare const DEFAULT_TEMPLATE_NAME = "default";
export declare const DEFAULT_LAYOUT_NAME = "default";
export declare const DEFAULT_TEMPLATE_SOURCE = "{{{body}}}";
export declare const DEFAULT_LAYOUT_SOURCE = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>{{title}}</title>\n</head>\n<body>\n<h1>{{title}}</h1>\n{{#if date}}<p class=\"date\">{{date}}</p>{{/if}}\n{{#if tags}}<ul class=\"tags\">{{#each tags}}<li>{{this}}</li>{{/each}}</ul>{{/if}}\n<div class=\"content\">\n{{{body}}}\n</div>\n</body>\n</html>\n";
export interface TemplateEngineOptions {
    defaultTemplate?: string;
    defaultLayout?: string;
}
export interface RenderContext {
    [key: string]: unknown;
}
export declare class TemplateEngine {
    private readonly handlebars;
    private readonly templatesDir;
    private readonly layoutsDir;
    private readonly partialsDir;
    private readonly defaultTemplate;
    private readonly defaultLayout;
    private readonly compiled;
    constructor(templatesDir: string, options?: TemplateEngineOptions);
    /**
     * Render a page: apply the page template (produces the body) and then wrap
     * the result with the layout template via the {{{body}}} placeholder.
     */
    render(templateName: string | undefined, layoutName: string | false | undefined, context: RenderContext): string;
    private resolveTemplate;
    private resolveLayout;
    private resolveFile;
    private compile;
    private registerPartials;
}
