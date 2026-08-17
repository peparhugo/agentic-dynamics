import { Plugin, PluginContext, PluginPipeline } from './plugin';
import { BuildOptions, Site } from './types';
export declare const DEFAULT_CONTENT_DIR = "content";
export declare const DEFAULT_OUTPUT_DIR = "dist";
export declare const DEFAULT_TEMPLATES_DIR = "templates";
/**
 * Assemble the plugin pipeline: the built-in markdown and template plugins run
 * first, followed by any plugins declared in the project configuration.
 */
export declare function buildPlugins(context: PluginContext): Plugin[];
export declare function createEngine(options: BuildOptions): {
    context: PluginContext;
    pipeline: PluginPipeline;
};
/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir. The core engine only
 * orchestrates the plugin pipeline; parsing and rendering are delegated to the
 * built-in MarkdownPlugin and TemplatePlugin.
 */
export declare function buildSite(options: BuildOptions): Site;
