import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';
/**
 * Built-in plugin that renders pages and the site index through Handlebars
 * templates.
 *
 * Templates are loaded during `beforeBuild`; each page is rendered in the
 * `onFile` hook and the index is rendered in `afterBuild`. Rendered output is
 * contributed to the engine's output files so the engine can write it to disk.
 */
export declare class TemplatePlugin implements Plugin {
    readonly name = "templates";
    beforeBuild(ctx: PluginContext): Promise<void>;
    onFile(page: Page, ctx: PluginContext): void;
    afterBuild(ctx: PluginContext): void;
}
