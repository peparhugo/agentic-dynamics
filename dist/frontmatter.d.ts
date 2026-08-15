export interface Frontmatter {
    title?: string;
    date?: string;
    tags?: string[] | string;
    template?: string;
    layout?: string;
    [key: string]: unknown;
}
export interface ParsedMarkdown {
    data: Frontmatter;
    body: string;
}
/**
 * Strips the leading YAML frontmatter block (delimited by `---`) using a
 * regex, then parses the YAML with gray-matter. Stripping manually before
 * handing the body to `marked` is required: otherwise `marked` renders the
 * `---` delimiter block as literal HTML text.
 */
export declare function parseFrontmatter(raw: string): ParsedMarkdown;
export declare function normalizeTags(tags: Frontmatter['tags']): string[];
