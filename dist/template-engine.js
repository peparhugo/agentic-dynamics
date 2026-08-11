"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createTemplateEngine = createTemplateEngine;
const handlebars_1 = __importDefault(require("handlebars"));
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
async function loadTemplateFiles(dir) {
    const map = new Map();
    let entries;
    try {
        const dirents = await fs_1.promises.readdir(dir, { withFileTypes: true });
        entries = dirents.map((e) => ({ name: e.name, isDirectory: e.isDirectory() }));
    }
    catch {
        return map;
    }
    for (const entry of entries) {
        if (entry.isDirectory)
            continue;
        const ext = path_1.default.extname(entry.name);
        if (ext !== ".hbs" && ext !== ".handlebars")
            continue;
        const name = path_1.default.basename(entry.name, ext);
        const templatePath = path_1.default.join(dir, entry.name);
        const source = await fs_1.promises.readFile(templatePath, "utf-8");
        map.set(name, handlebars_1.default.compile(source));
    }
    return map;
}
async function loadPartials(dir) {
    let entries;
    try {
        const dirents = await fs_1.promises.readdir(dir, { withFileTypes: true });
        entries = dirents.map((e) => ({ name: e.name, isDirectory: e.isDirectory() }));
    }
    catch {
        return;
    }
    for (const entry of entries) {
        if (entry.isDirectory)
            continue;
        const ext = path_1.default.extname(entry.name);
        if (ext !== ".hbs" && ext !== ".handlebars")
            continue;
        const name = path_1.default.basename(entry.name, ext);
        const templatePath = path_1.default.join(dir, entry.name);
        const source = await fs_1.promises.readFile(templatePath, "utf-8");
        handlebars_1.default.registerPartial(name, source);
    }
}
async function createTemplateEngine(templatesDir) {
    const absDir = path_1.default.resolve(templatesDir);
    try {
        await fs_1.promises.access(absDir);
    }
    catch {
        return null;
    }
    const partialsDir = path_1.default.join(absDir, "partials");
    await loadPartials(partialsDir);
    const layoutDir = path_1.default.join(absDir, "layouts");
    const [templates, layouts] = await Promise.all([
        loadTemplateFiles(absDir),
        loadTemplateFiles(layoutDir),
    ]);
    if (templates.size === 0 && layouts.size === 0) {
        return null;
    }
    const compiled = { templates, layouts };
    return {
        renderPage(frontmatter, content, template, layout) {
            const templateData = {
                ...frontmatter,
                content,
            };
            const pageLayout = layout || frontmatter.layout;
            const pageTemplate = template || frontmatter.template || "default";
            let rendered;
            const tpl = compiled.templates.get(pageTemplate) ||
                (pageTemplate === "default"
                    ? compiled.templates.values().next().value
                    : undefined);
            if (tpl) {
                rendered = tpl(templateData);
            }
            else {
                compiled.templates.values().next().value;
                const firstTpl = compiled.templates.values().next().value;
                if (firstTpl) {
                    rendered = firstTpl(templateData);
                }
                else {
                    return content;
                }
            }
            if (pageLayout) {
                const layoutTpl = compiled.layouts.get(pageLayout);
                if (layoutTpl) {
                    rendered = layoutTpl({ ...templateData, body: rendered });
                }
            }
            return rendered;
        },
        renderIndex(pages) {
            const indexTpl = compiled.templates.get("index");
            if (!indexTpl) {
                return "";
            }
            const items = pages.map((page) => ({
                href: page.path.replace(/\.md$/, ".html"),
                title: page.frontmatter.title || page.path,
                date: page.frontmatter.date || "",
                tags: page.frontmatter.tags || "",
            }));
            return indexTpl({ pages: items });
        },
    };
}
