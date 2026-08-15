import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';
/**
 * Built-in plugin that parses raw Markdown content into structured pages.
 *
 * Runs during the `onFile` hook: it reads the raw source (frontmatter +
 * body) handed to it by the engine and replaces the placeholder page with
 * fully parsed page data, leaving template/layout rendering to later plugins.
 */
export declare class MarkdownPlugin implements Plugin {
    readonly name = "markdown";
    onFile(page: Page, _ctx: PluginContext): Promise<void>;
}
