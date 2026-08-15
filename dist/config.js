"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.defineConfig = defineConfig;
exports.normalizeConfig = normalizeConfig;
exports.loadConfig = loadConfig;
exports.loadConfigFile = loadConfigFile;
exports.resolvePlugins = resolvePlugins;
const path_1 = __importDefault(require("path"));
const fs_1 = require("fs");
const plugin_1 = require("./plugin");
const loaders_1 = require("./loaders");
function defineConfig(config) {
    return config;
}
function normalizeConfig(raw) {
    if (!raw || typeof raw !== 'object') {
        return {};
    }
    const config = raw;
    if (config.plugins == null) {
        return {};
    }
    const plugins = Array.isArray(config.plugins) ? config.plugins : [config.plugins];
    return { plugins };
}
const CONFIG_FILENAMES = [
    'ssg.config.ts',
    'ssg.config.mts',
    'ssg.config.js',
    'ssg.config.cjs',
    'ssg.config.mjs',
    'ssg.config.json',
];
async function loadConfig(cwd = process.cwd()) {
    for (const name of CONFIG_FILENAMES) {
        const filePath = path_1.default.join(cwd, name);
        if (!(0, fs_1.existsSync)(filePath)) {
            continue;
        }
        try {
            const loaded = await (0, loaders_1.loadModule)(filePath);
            const exported = unwrapDefault(loaded);
            const resolved = typeof exported === 'function' ? await exported() : exported;
            return normalizeConfig(resolved);
        }
        catch {
            continue;
        }
    }
    return {};
}
async function loadConfigFile(filePath) {
    const loaded = await (0, loaders_1.loadModule)(path_1.default.resolve(filePath));
    const exported = unwrapDefault(loaded);
    const resolved = typeof exported === 'function' ? await exported() : exported;
    return normalizeConfig(resolved);
}
function unwrapDefault(mod) {
    if (mod && typeof mod === 'object' && 'default' in mod) {
        return mod.default;
    }
    return mod;
}
const BUILTIN_PLUGIN_NAMES = new Set(['markdown', 'template', 'devServer']);
async function resolvePlugins(entries, baseDir) {
    const resolved = [];
    for (const entry of entries ?? []) {
        for (const plugin of await resolvePluginEntry(entry, baseDir)) {
            resolved.push(plugin);
        }
    }
    return resolved;
}
async function resolvePluginEntry(entry, baseDir) {
    if (typeof entry === 'string') {
        if (BUILTIN_PLUGIN_NAMES.has(entry)) {
            return [];
        }
        const filePath = resolvePluginPath(baseDir, entry);
        if (!filePath) {
            return [];
        }
        try {
            return await flattenPluginExport(await (0, loaders_1.loadModule)(filePath));
        }
        catch {
            return [];
        }
    }
    if (typeof entry === 'function') {
        return flattenPluginExport(await entry());
    }
    if ((0, plugin_1.isPlugin)(entry)) {
        return [entry];
    }
    return [];
}
function resolvePluginPath(baseDir, entry) {
    const abs = path_1.default.isAbsolute(entry) ? entry : path_1.default.resolve(baseDir, entry);
    const candidates = [
        abs,
        `${abs}.ts`,
        `${abs}.tsx`,
        `${abs}.js`,
        `${abs}.cjs`,
        `${abs}.mjs`,
        path_1.default.join(abs, 'index.ts'),
        path_1.default.join(abs, 'index.js'),
        path_1.default.join(abs, 'index.json'),
    ];
    for (const candidate of candidates) {
        if ((0, fs_1.existsSync)(candidate)) {
            return candidate;
        }
    }
    return undefined;
}
async function flattenPluginExport(mod) {
    const exported = unwrapDefault(mod);
    if (typeof exported === 'function') {
        return flattenPluginExport(await exported());
    }
    if (Array.isArray(exported)) {
        const out = [];
        for (const item of exported) {
            out.push(...(await flattenPluginExport(item)));
        }
        return out;
    }
    if ((0, plugin_1.isPlugin)(exported)) {
        return [exported];
    }
    return [];
}
//# sourceMappingURL=config.js.map