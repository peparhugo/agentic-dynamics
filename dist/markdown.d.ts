import { Frontmatter } from './types';
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
export declare function normalizeDate(value: unknown): string | undefined;
/**
 * Parse raw markdown (with optional frontmatter) into frontmatter data and
 * rendered HTML. The returned HTML is a document fragment (no <html>/<body>).
 */
export declare function parseMarkdown(raw: string): {
    frontmatter: Frontmatter;
    html: string;
};
export declare function escapeHtml(input: string): string;
export declare function normalizeTags(tags: unknown): string[];
export declare function defaultTitle(slug: string): string;
