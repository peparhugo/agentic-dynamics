"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.runHook = runHook;
exports.runHooks = runHooks;
exports.loadPluginModule = loadPluginModule;
exports.toPlugin = toPlugin;
exports.loadConfig = loadConfig;
exports.pluginsFromConfig = pluginsFromConfig;
exports.discoverPlugins = discoverPlugins;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
function runHook(plugin, hook, ctx, result) {
    if (hook === 'afterBuild') {
        if (typeof plugin.afterBuild === 'function') {
            plugin.afterBuild.call(plugin, ctx, result);
        }
        return;
    }
    if (hook === 'onFile') {
        if (typeof plugin.onFile === 'function') {
            const page = ctx.pages && ctx.pages.length > 0 ? ctx.pages[0] : {};
            plugin.onFile.call(plugin, page, ctx);
        }
        return;
    }
    const fn = plugin[hook];
    if (typeof fn === 'function') {
        fn.call(plugin, ctx);
    }
}
function runHooks(plugins, hook, ctx, result) {
    for (const plugin of plugins) {
        runHook(plugin, hook, ctx, result);
    }
}
function isPluginObject(value) {
    if (!value || typeof value !== 'object' || typeof value === 'function') {
        return false;
    }
    const maybe = value;
    return typeof maybe.name === 'string' && maybe.name.length > 0;
}
function resolveModulePath(cwd, spec) {
    const base = path_1.default.resolve(cwd);
    let full = path_1.default.isAbsolute(spec) ? spec : path_1.default.resolve(base, spec);
    const candidates = [];
    if (!path_1.default.extname(full)) {
        for (const ext of ['.ts', '.js', '.cjs', '.mjs'])
            candidates.push(full + ext);
        candidates.push(path_1.default.join(full, 'index.ts'));
        candidates.push(path_1.default.join(full, 'index.js'));
    }
    else {
        candidates.push(full);
    }
    for (const candidate of candidates) {
        if (fs_1.default.existsSync(candidate))
            return candidate;
    }
    return full;
}
function loadPluginModule(cwd, spec) {
    const rel = typeof spec === 'string' ? spec : (spec.path ?? spec.module ?? '');
    if (!rel)
        return null;
    let full = path_1.default.isAbsolute(rel) ? rel : path_1.default.resolve(cwd, rel);
    if (!fs_1.default.existsSync(full)) {
        const inPlugins = path_1.default.resolve(cwd, 'plugins', rel);
        if (fs_1.default.existsSync(inPlugins) || fs_1.default.existsSync(resolveModulePath(cwd, inPlugins))) {
            full = inPlugins;
        }
        else {
            full = resolveModulePath(cwd, rel);
        }
    }
    if (!fs_1.default.existsSync(full))
        return null;
    const mod = require(full);
    return toPlugin(mod.default ?? mod);
}
function toPlugin(value) {
    if (value == null)
        return null;
    if (isPluginObject(value))
        return value;
    if (typeof value === 'function') {
        try {
            const instance = new value();
            return isPluginObject(instance) ? instance : null;
        }
        catch {
            return null;
        }
    }
    if (typeof value === 'string') {
        return null;
    }
    return null;
}
function loadConfig(cwd, configFile) {
    const name = configFile ?? 'ssg.config.ts';
    const resolved = resolveModulePath(cwd, name);
    if (!fs_1.default.existsSync(resolved))
        return {};
    const mod = require(resolved);
    const cfg = (mod.default ?? mod);
    return cfg && typeof cfg === 'object' ? cfg : {};
}
function pluginsFromConfig(config) {
    const raw = config.plugins;
    if (!Array.isArray(raw))
        return [];
    const plugins = [];
    for (const entry of raw) {
        const plugin = toPlugin(entry);
        if (plugin) {
            plugins.push(plugin);
        }
        else if (typeof entry === 'string') {
            const loaded = loadPluginModule(process.cwd(), entry);
            if (loaded)
                plugins.push(loaded);
        }
    }
    return plugins;
}
function discoverPlugins(cwd) {
    const dir = path_1.default.resolve(cwd, 'plugins');
    if (!fs_1.default.existsSync(dir))
        return [];
    const plugins = [];
    const entries = fs_1.default.readdirSync(dir).sort();
    for (const entry of entries) {
        if (!/\.(ts|js|cjs|mjs)$/.test(entry))
            continue;
        if (/\.(test|spec)\./.test(entry))
            continue;
        if (entry === 'index.ts' || entry === 'index.js')
            continue;
        const full = path_1.default.join(dir, entry);
        const mod = require(full);
        const plugin = toPlugin(mod.default ?? mod);
        if (plugin)
            plugins.push(plugin);
    }
    return plugins;
}
