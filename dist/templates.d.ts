export interface PageContext {
    title: string;
    date?: string;
    tags: string[];
    slug: string;
    content: string;
    body: string;
    [key: string]: unknown;
}
/**
 * A Handlebars-based template engine scoped to a single `templates` directory.
 *
 * It discovers layout templates from `templates/layouts/*.hbs` and reusable
 * partials from `templates/partials/*.hbs`. Each instance uses its own
 * isolated Handlebars environment so multiple builds never leak state.
 */
export declare class TemplateEngine {
    private templatesDir;
    private hbs;
    private layouts;
    private defaultLayout;
    constructor(templatesDir: string);
    private registerPartials;
    private registerLayouts;
    get availableLayouts(): string[];
    hasLayout(name: string): boolean;
    /**
     * Render a page using the requested layout (falling back to the default
     * layout). Returns `null` when no matching layout exists so the caller can
     * fall back to its built-in HTML rendering.
     */
    render(templateName: string | undefined, context: PageContext): string | null;
}
