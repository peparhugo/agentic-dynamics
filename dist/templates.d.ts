export interface PageContext {
    title: string;
    date?: string;
    tags: string[];
    slug: string;
    content: string;
    body: string;
    [key: string]: unknown;
}
export declare function normalizeTemplateName(name: string): string;
/**
 * Computes a stable fingerprint for the template output a page resolves to.
 *
 * It hashes the resolved layout file (honouring the page's `template` name and
 * the `default` fallback) plus every registered partial. This mirrors the
 * resolution performed by {@link TemplateEngine.render} so the fingerprint only
 * changes when the actual rendered template would change.
 */
export declare function templateFingerprint(templatesDir: string, requestedTemplate: string | undefined): string;
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
