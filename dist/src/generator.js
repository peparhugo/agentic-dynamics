"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const config_1 = require("./config");
const loader_1 = require("./loader");
const engine_1 = require("./engine");
/**
 * Build a static site from Markdown content.
 *
 * Delegates to the core SSG engine, which orchestrates the plugin pipeline
 * (markdown parsing, template rendering, and any configured plugins).
 */
async function build(options) {
    const config = await (0, config_1.loadConfig)();
    const plugins = await (0, loader_1.loadPlugins)(config);
    const engine = new engine_1.SsgEngine(plugins, options, config);
    return engine.build();
}
