"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.PLUGIN_DIR = void 0;
exports.loadPlugins = loadPlugins;
const path = __importStar(require("path"));
const module_loader_1 = require("./module-loader");
const markdown_1 = require("../plugins/markdown");
const templates_1 = require("../plugins/templates");
exports.PLUGIN_DIR = 'plugins';
function resolvePluginFile(entry) {
    const base = path.join(path.resolve(process.cwd(), exports.PLUGIN_DIR), entry);
    return path.extname(base) ? base : `${base}.ts`;
}
function instantiate(entry) {
    let resolved;
    try {
        resolved = (0, module_loader_1.loadTsModule)(resolvePluginFile(entry));
    }
    catch {
        throw new Error(`plugin not found: ${entry}`);
    }
    if (typeof resolved === 'function') {
        return new resolved();
    }
    if (resolved && typeof resolved === 'object') {
        return resolved;
    }
    throw new Error(`plugin not found: ${entry}`);
}
/**
 * Build the plugin list. Built-in plugins (markdown, templates) are always
 * registered first; plugins configured in `ssg.config.ts` are appended in
 * order, so every hook runs across all of them sequentially.
 */
async function loadPlugins(config) {
    const plugins = [new markdown_1.MarkdownPlugin(), new templates_1.TemplatePlugin()];
    const configured = config.plugins ?? [];
    for (const entry of configured) {
        if (typeof entry === 'string') {
            plugins.push(instantiate(entry));
        }
        else if (entry) {
            plugins.push(entry);
        }
    }
    return plugins;
}
