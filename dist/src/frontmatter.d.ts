import { ParsedFrontmatter } from './types';
/**
 * Extract a `---`-delimited YAML frontmatter block from the top of a file.
 * Returns the raw YAML string (without delimiters) or null when absent.
 */
export declare function extractFrontmatterBlock(raw: string): string | null;
/**
 * Parse a `---`-delimited YAML frontmatter block.
 *
 * YAML frontmatter is unsupported by gray-matter out of the box, so we parse
 * the block ourselves with a simple `key: value` splitter. Scalars (strings,
 * numbers, booleans), dates, and simple comma-separated lists are supported.
 */
export declare function parseFrontmatter(raw: string): ParsedFrontmatter;
/** Parse a plain `key: value` YAML block into a record. */
export declare function parseYamlBlock(block: string): ParsedFrontmatter;
