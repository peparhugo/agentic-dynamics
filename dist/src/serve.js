"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.injectReloadScript = void 0;
exports.serve = serve;
const build_1 = require("./build");
const dev_server_plugin_1 = require("../plugins/dev-server-plugin");
var dev_server_plugin_2 = require("../plugins/dev-server-plugin");
Object.defineProperty(exports, "injectReloadScript", { enumerable: true, get: function () { return dev_server_plugin_2.injectReloadScript; } });
function serve(options) {
    const contentDir = options.content || './content';
    const outputDir = options.output || './dist';
    const templatesDir = options.templates || './templates';
    const port = options.port || 3000;
    const devPlugin = new dev_server_plugin_1.DevServerPlugin();
    (0, build_1.build)(contentDir, outputDir, templatesDir);
    devPlugin.setContext({
        contentDir,
        outputDir,
        templatesDir,
    });
    devPlugin.onStart();
    return devPlugin.listen(port);
}
//# sourceMappingURL=serve.js.map