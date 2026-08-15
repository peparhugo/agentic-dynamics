"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const config_1 = require("./config");
const markdown_plugin_1 = require("./plugins/markdown-plugin");
const template_plugin_1 = require("./plugins/template-plugin");
const render_1 = require("./render");
function listMarkdownFiles(dir) {
    const files = [];
    if (!fs_1.default.existsSync(dir)) {
        return files;
    }
    for (const entry of fs_1.default.readdirSync(dir)) {
        const fullPath = path_1.default.join(dir, entry);
        const stat = fs_1.default.statSync(fullPath);
        if (stat.isDirectory()) {
            files.push(...listMarkdownFiles(fullPath));
        }
        else if (stat.isFile() && /\.md$/i.test(entry)) {
            files.push(fullPath);
        }
    }
    return files;
}
function slugForFile(filePath, contentDir) {
    const relative = path_1.default.relative(contentDir, filePath);
    const withoutExtension = relative.replace(/\.md$/i, '');
    return withoutExtension.split(path_1.default.sep).join('/');
}
function sortPosts(posts) {
    posts.sort((a, b) => {
        const dateA = a.date ? Date.parse(a.date) : NaN;
        const dateB = b.date ? Date.parse(b.date) : NaN;
        if (!Number.isNaN(dateA) && !Number.isNaN(dateB) && dateA !== dateB) {
            return dateB - dateA;
        }
        if (Number.isNaN(dateA) && !Number.isNaN(dateB)) {
            return 1;
        }
        if (!Number.isNaN(dateA) && Number.isNaN(dateB)) {
            return -1;
        }
        return a.title.localeCompare(b.title);
    });
}
function runHooksSync(plugins, method) {
    for (const plugin of plugins) {
        const hook = plugin[method];
        if (typeof hook !== 'function') {
            continue;
        }
        const result = hook.call(plugin);
        if (result != null && typeof result.then === 'function') {
            throw new Error(`Plugin "${plugin.name ?? 'unnamed'}" returned a Promise from "${method}". ` +
                'Asynchronous plugin hooks are not supported by the synchronous build pipeline.');
        }
    }
}
function runFileHooksSync(plugins, page) {
    for (const plugin of plugins) {
        const hook = plugin.onFile;
        if (typeof hook !== 'function') {
            continue;
        }
        const result = hook.call(plugin, page);
        if (result != null && typeof result.then === 'function') {
            throw new Error(`Plugin "${plugin.name ?? 'unnamed'}" returned a Promise from "onFile". ` +
                'Asynchronous plugin hooks are not supported by the synchronous build pipeline.');
        }
    }
}
/**
 * Build a static site by running the plugin pipeline.
 *
 * The built-in `MarkdownPlugin` and `TemplatePlugin` always run first (in that
 * order), followed by any plugins passed via `options.plugins` and any plugins
 * declared in the project's `ssg.config.ts`.
 */
function buildSite(options) {
    const { contentDir, outputDir } = options;
    const templatesDir = options.templatesDir ?? path_1.default.join(process.cwd(), 'templates');
    const configDir = options.configDir ?? process.cwd();
    const plugins = [
        new markdown_plugin_1.MarkdownPlugin(),
        new template_plugin_1.TemplatePlugin(templatesDir),
        ...(options.plugins ?? []),
        ...(0, config_1.loadPlugins)(configDir),
    ];
    runHooksSync(plugins, 'onStart');
    runHooksSync(plugins, 'beforeBuild');
    const markdownFiles = listMarkdownFiles(contentDir);
    const pages = markdownFiles.map((filePath) => {
        const slug = slugForFile(filePath, contentDir);
        const source = fs_1.default.readFileSync(filePath, 'utf-8');
        return {
            slug,
            title: '',
            date: undefined,
            tags: [],
            template: undefined,
            content: source,
            html: '',
        };
    });
    for (const page of pages) {
        runFileHooksSync(plugins, page);
    }
    sortPosts(pages);
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const filesWritten = [];
    const indexPath = path_1.default.join(outputDir, 'index.html');
    fs_1.default.writeFileSync(indexPath, (0, render_1.renderIndex)(pages));
    filesWritten.push(indexPath);
    for (const page of pages) {
        const pagePath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.mkdirSync(path_1.default.dirname(pagePath), { recursive: true });
        fs_1.default.writeFileSync(pagePath, page.rendered ?? '');
        filesWritten.push(pagePath);
    }
    runHooksSync(plugins, 'afterBuild');
    runHooksSync(plugins, 'onEnd');
    const posts = pages.map((page) => ({
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        template: page.template,
        content: page.content,
        html: page.html,
    }));
    return { posts, filesWritten, outputDir };
}
