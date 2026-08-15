"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.installTypeScriptRequireHook = installTypeScriptRequireHook;
exports.loadConfig = loadConfig;
exports.loadPlugins = loadPlugins;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.mjs', 'ssg.config.cjs'];
let tsHookInstalled = false;
function compileTypeScript(source) {
    const ts = require('typescript');
    return ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2020,
            esModuleInterop: true,
            moduleResolution: ts.ModuleResolutionKind.NodeJs,
        },
    }).outputText;
}
/**
 * Registers a `require` extension for `.ts` files so that `ssg.config.ts` and
 * its plugin modules (which live in `./plugins/*.ts`) can be loaded at runtime.
 * No-op when TypeScript support is already registered (ts-node, ts-jest, ...).
 */
function installTypeScriptRequireHook() {
    if (tsHookInstalled) {
        return;
    }
    tsHookInstalled = true;
    const extensions = require.extensions;
    if (typeof extensions['.ts'] === 'function') {
        return;
    }
    extensions['.ts'] = (mod, filename) => {
        const source = fs_1.default.readFileSync(filename, 'utf-8');
        mod._compile(compileTypeScript(source), filename);
    };
}
function findConfigFile(dir) {
    for (const name of CONFIG_FILENAMES) {
        const candidate = path_1.default.join(dir, name);
        if (fs_1.default.existsSync(candidate)) {
            return candidate;
        }
    }
    return undefined;
}
function unwrapDefault(loaded) {
    if (loaded && typeof loaded === 'object' && 'default' in loaded) {
        return loaded.default;
    }
    return loaded;
}
/**
 * Loads and evaluates a `ssg.config.ts` (or `.js`/`.mjs`/`.cjs`) file from the
 * given directory, returning the exported configuration object.
 */
function loadConfig(dir = process.cwd()) {
    const filePath = findConfigFile(dir);
    if (!filePath) {
        return {};
    }
    installTypeScriptRequireHook();
    const resolved = path_1.default.resolve(filePath);
    delete require.cache[resolved];
    let config = unwrapDefault(require(resolved));
    if (typeof config === 'function') {
        config = config();
    }
    if (config == null || typeof config !== 'object') {
        return {};
    }
    return config;
}
/**
 * Loads the plugin instances declared in the `ssg.config.ts` file located in
 * the given directory.
 */
function loadPlugins(dir = process.cwd()) {
    const config = loadConfig(dir);
    const plugins = config.plugins ?? [];
    return plugins.filter((plugin) => !!plugin);
}
