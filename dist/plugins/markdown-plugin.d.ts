import { Page, Plugin } from '../plugin';
/**
 * Built-in plugin that parses Markdown documents.
 *
 * The engine creates each `Page` with the raw file source in `content`. This
 * plugin parses the frontmatter, rewrites `content` to the stripped Markdown
 * body and fills `html` with the rendered body HTML.
 */
export declare class MarkdownPlugin implements Plugin {
    name: string;
    onFile(page: Page): void;
}
