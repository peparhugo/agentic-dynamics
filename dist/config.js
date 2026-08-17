"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadConfig = loadConfig;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js'];
/**
 * Load the project configuration from ssg.config.ts (or a compiled
 * ssg.config.js fallback). A raw TypeScript config can only be required when a
 * runtime loader (ts-node/tsx) is active, so unloadable files are skipped.
 */
function loadConfig(cwd) {
    for (const filename of CONFIG_FILENAMES) {
        const file = path_1.default.join(cwd, filename);
        if (!fs_1.default.existsSync(file)) {
            continue;
        }
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const loaded = require(file);
            return normalizeConfig(loaded && 'default' in loaded ? loaded.default : loaded);
        }
        catch {
            // Ignore configs that cannot be loaded at runtime.
        }
    }
    return {};
}
function normalizeConfig(raw) {
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        const plugins = raw.plugins;
        if (Array.isArray(plugins)) {
            return { plugins: plugins.filter((p) => typeof p === 'string') };
        }
    }
    return {};
}
//# sourceMappingURL=config.js.map