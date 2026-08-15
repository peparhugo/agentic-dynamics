"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.injectLiveReload = exports.liveReloadScript = void 0;
exports.serve = serve;
const path_1 = __importDefault(require("path"));
const config_1 = require("./config");
const engine_1 = require("./engine");
const devServer_1 = require("./plugins/devServer");
const liveReload_1 = require("./liveReload");
Object.defineProperty(exports, "liveReloadScript", { enumerable: true, get: function () { return liveReload_1.liveReloadScript; } });
Object.defineProperty(exports, "injectLiveReload", { enumerable: true, get: function () { return liveReload_1.injectLiveReload; } });
async function resolveServeConfig(options) {
    if (options.config === false) {
        return { config: {}, baseDir: process.cwd() };
    }
    if (typeof options.config === 'string') {
        const filePath = path_1.default.resolve(options.config);
        return { config: await (0, config_1.loadConfigFile)(filePath), baseDir: path_1.default.dirname(filePath) };
    }
    const cwd = process.cwd();
    return { config: await (0, config_1.loadConfig)(cwd), baseDir: cwd };
}
async function serve(options) {
    const { config, baseDir } = await resolveServeConfig(options);
    const configPlugins = await (0, config_1.resolvePlugins)(config.plugins, baseDir);
    const plugins = [...configPlugins, ...(options.plugins ?? [])];
    const engine = new engine_1.SsgEngine(options, config, plugins);
    const devServer = new devServer_1.DevServerPlugin(engine);
    return devServer.start(options);
}
//# sourceMappingURL=serve.js.map