"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadPluginsFromConfig = loadPluginsFromConfig;
const path_1 = __importDefault(require("path"));
function loadPluginsFromConfig() {
    try {
        const configPath = path_1.default.join(process.cwd(), 'ssg.config');
        const config = require(configPath);
        const plugins = config?.default?.plugins || config?.plugins || [];
        if (Array.isArray(plugins))
            return plugins;
        return [];
    }
    catch {
        return [];
    }
}
//# sourceMappingURL=plugin.js.map