import { Plugin, PluginContext } from '../plugin';
/**
 * Built-in plugin that renders each page through the template engine and writes
 * the resulting HTML to the output directory. Rendering happens on the
 * `afterBuild` hook so every page (and its metadata) is available for the
 * `site.pages` context used by templates and partials.
 */
export declare class TemplatePlugin implements Plugin {
    private readonly context;
    name: string;
    private readonly engine;
    constructor(context: PluginContext);
    afterBuild(): void;
}
