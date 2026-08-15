"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.reloadClientScript = exports.injectReloadScript = void 0;
exports.startDevServer = startDevServer;
const config_1 = require("./config");
const loader_1 = require("./loader");
const engine_1 = require("./engine");
const devserver_1 = require("../plugins/devserver");
var livereload_1 = require("./livereload");
Object.defineProperty(exports, "injectReloadScript", { enumerable: true, get: function () { return livereload_1.injectReloadScript; } });
Object.defineProperty(exports, "reloadClientScript", { enumerable: true, get: function () { return livereload_1.reloadClientScript; } });
/**
 * Start a live-reload development server.
 *
 * Delegates to the core SSG engine with the dev-server plugin loaded, which
 * performs an initial build, serves the built site from `outputDir`, watches
 * `contentDir` and `templatesDir` for changes, rebuilds on change, and tells
 * connected browsers to reload once a rebuild finishes.
 */
async function startDevServer(options) {
    const config = await (0, config_1.loadConfig)();
    const plugins = await (0, loader_1.loadPlugins)(config);
    plugins.push(new devserver_1.DevServerPlugin());
    const engine = new engine_1.SsgEngine(plugins, options, config);
    return (await engine.serve());
}
