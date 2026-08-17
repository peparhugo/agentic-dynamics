export interface Frontmatter {
    title?: string;
    date?: string;
    tags?: string[];
    template?: string;
    layout?: string | false;
    [key: string]: unknown;
}
export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    html: string;
    sourcePath: string;
    frontmatter: Frontmatter;
    template?: string;
    layout?: string | false;
}
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    defaultTemplate?: string;
    defaultLayout?: string;
}
export interface Site {
    pages: Page[];
    outputDir: string;
}
/**
 * Split raw markdown into frontmatter data and the markdown body.
 *
 * The frontmatter block is stripped manually with a regex before the body is
 * handed to `marked`, otherwise `marked` renders the `---` delimiters as a
 * literal horizontal rule. gray-matter is used only to parse the YAML data.
 */
export declare function splitFrontmatter(raw: string): {
    data: Frontmatter;
    body: string;
};
/**
 * Parse raw markdown (with optional frontmatter) into frontmatter data and
 * rendered HTML. The returned HTML is a document fragment (no <html>/<body>).
 */
export declare function parseMarkdown(raw: string): {
    frontmatter: Frontmatter;
    html: string;
};
export declare function escapeHtml(input: string): string;
/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir.
 */
export declare function buildSite(options: BuildOptions): Site;
