"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const path_1 = __importDefault(require("path"));
const config_1 = require("./config");
const engine_1 = require("./engine");
async function resolveBuildConfig(options) {
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
async function build(options) {
    const { config, baseDir } = await resolveBuildConfig(options);
    const configPlugins = await (0, config_1.resolvePlugins)(config.plugins, baseDir);
    const plugins = [...configPlugins, ...(options.plugins ?? [])];
    const engine = new engine_1.SsgEngine(options, config, plugins);
    return engine.run();
}
//# sourceMappingURL=build.js.map