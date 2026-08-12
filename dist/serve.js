"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.broadcastReload = exports.createRequestHandler = exports.injectLiveReload = exports.hasLiveReload = exports.clientScript = exports.DevServerPlugin = exports.REBUILD_DELAY_MS = exports.RELOAD_MESSAGE = exports.LIVERELOAD_PATH = exports.DEFAULT_PORT = void 0;
exports.serve = serve;
const engine_1 = require("./engine");
const devServer_1 = require("./plugins/devServer");
Object.defineProperty(exports, "DEFAULT_PORT", { enumerable: true, get: function () { return devServer_1.DEFAULT_PORT; } });
Object.defineProperty(exports, "LIVERELOAD_PATH", { enumerable: true, get: function () { return devServer_1.LIVERELOAD_PATH; } });
Object.defineProperty(exports, "RELOAD_MESSAGE", { enumerable: true, get: function () { return devServer_1.RELOAD_MESSAGE; } });
Object.defineProperty(exports, "REBUILD_DELAY_MS", { enumerable: true, get: function () { return devServer_1.REBUILD_DELAY_MS; } });
Object.defineProperty(exports, "DevServerPlugin", { enumerable: true, get: function () { return devServer_1.DevServerPlugin; } });
Object.defineProperty(exports, "clientScript", { enumerable: true, get: function () { return devServer_1.clientScript; } });
Object.defineProperty(exports, "hasLiveReload", { enumerable: true, get: function () { return devServer_1.hasLiveReload; } });
Object.defineProperty(exports, "injectLiveReload", { enumerable: true, get: function () { return devServer_1.injectLiveReload; } });
Object.defineProperty(exports, "createRequestHandler", { enumerable: true, get: function () { return devServer_1.createRequestHandler; } });
Object.defineProperty(exports, "broadcastReload", { enumerable: true, get: function () { return devServer_1.broadcastReload; } });
function serve(options) {
    const engine = new engine_1.SiteEngine({
        contentDir: options.contentDir,
        outputDir: options.outputDir,
        templatesDir: options.templatesDir,
        devServer: true,
    });
    return engine.serve(options);
}
