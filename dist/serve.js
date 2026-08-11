"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.serve = serve;
const ssg_1 = require("./ssg");
const dev_server_plugin_1 = require("./plugins/dev-server-plugin");
function serve(options) {
    const { contentDir, outputDir, templateDir } = options;
    const engine = new ssg_1.SSGEngine({ contentDir, outputDir, templateDir });
    engine.build();
    const devServer = new dev_server_plugin_1.DevServerPlugin();
    devServer.setEngine(engine);
    return devServer.start(options);
}
//# sourceMappingURL=serve.js.map