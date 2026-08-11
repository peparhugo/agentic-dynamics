"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadPlugins = loadPlugins;
exports.setPlugins = setPlugins;
const path_1 = __importDefault(require("path"));
let cachedPlugins = null;
function loadPlugins() {
    if (cachedPlugins)
        return cachedPlugins;
    const configPath = path_1.default.resolve(process.cwd(), 'ssg.config');
    try {
        const mod = require(configPath);
        const config = mod.default || mod;
        if (Array.isArray(config.plugins)) {
            cachedPlugins = config.plugins;
            return cachedPlugins;
        }
    }
    catch {
        // config not found, use built-ins
    }
    const { builtInPlugins } = require('./plugins');
    cachedPlugins = builtInPlugins;
    return cachedPlugins;
}
function setPlugins(plugins) {
    cachedPlugins = plugins;
}
//# sourceMappingURL=plugin.js.map