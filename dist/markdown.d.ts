import { ParsedMarkdown } from './types';
export declare function normalizeTags(tags: unknown): string[];
export declare function renderMarkdown(content: string): string;
/**
 * Parse a Markdown document with YAML frontmatter.
 *
 * gray-matter strips the `---` delimited frontmatter and returns the body in
 * `content`. We only ever pass that stripped body to `marked`, so the
 * frontmatter delimiter is never rendered as literal HTML.
 */
export declare function parseMarkdown(source: string): ParsedMarkdown;
