import { Page } from './types';
/**
 * Parse a Markdown source string into structured page data.
 *
 * gray-matter only parses JSON frontmatter, so we parse the `---`-delimited
 * YAML block ourselves and merge it into gray-matter's output before handing
 * the data to the renderer.
 */
export declare function parseMarkdown(source: string, sourcePath: string, slug: string): Page;
