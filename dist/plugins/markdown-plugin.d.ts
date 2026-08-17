import { Plugin } from '../plugin';
import { Page } from '../types';
/**
 * Built-in plugin that parses raw markdown (with optional frontmatter) into
 * the page's HTML and metadata. Registered on the `onFile` hook so it runs for
 * every discovered markdown file.
 */
export declare class MarkdownPlugin implements Plugin {
    name: string;
    onFile(page: Page): void;
}
