"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.injectLiveReloadScript = exports.LIVE_RELOAD_SCRIPT = exports.RELOAD_MESSAGE = void 0;
exports.startDevServer = startDevServer;
const index_1 = require("./index");
const dev_server_plugin_1 = require("./plugins/dev-server-plugin");
Object.defineProperty(exports, "RELOAD_MESSAGE", { enumerable: true, get: function () { return dev_server_plugin_1.RELOAD_MESSAGE; } });
Object.defineProperty(exports, "LIVE_RELOAD_SCRIPT", { enumerable: true, get: function () { return dev_server_plugin_1.LIVE_RELOAD_SCRIPT; } });
Object.defineProperty(exports, "injectLiveReloadScript", { enumerable: true, get: function () { return dev_server_plugin_1.injectLiveReloadScript; } });
/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the generated site from outputDir over
 * HTTP, injects a WebSocket client script into HTML responses, watches the
 * content and templates directories for changes, rebuilds on change, and tells
 * connected browsers to reload when a rebuild completes.
 */
async function startDevServer(options = {}) {
    const plugin = new dev_server_plugin_1.DevServerPlugin(index_1.buildSite, options);
    return plugin.start();
}
//# sourceMappingURL=serve.js.map