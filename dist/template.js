"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.setTemplateDir = setTemplateDir;
exports.setDefaultLayout = setDefaultLayout;
exports.createTemplateEngine = createTemplateEngine;
exports.getEngine = getEngine;
exports.loadPartials = loadPartials;
exports.loadTemplate = loadTemplate;
exports.loadLayout = loadLayout;
exports.renderPage = renderPage;
const handlebars_1 = __importDefault(require("handlebars"));
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
let defaultTemplateDir = './templates';
let defaultLayoutName = 'default';
let engine = null;
function setTemplateDir(dir) {
    defaultTemplateDir = dir;
}
function setDefaultLayout(name) {
    defaultLayoutName = name;
}
function createTemplateEngine() {
    return {
        registerPartial(name, content) {
            handlebars_1.default.registerPartial(name, content);
        },
        render(templateContent, data) {
            const template = handlebars_1.default.compile(templateContent);
            return template(data);
        }
    };
}
function getEngine() {
    if (!engine) {
        engine = createTemplateEngine();
    }
    return engine;
}
async function loadPartials(templateDir) {
    const partialsDir = path_1.default.join(templateDir, 'partials');
    const eng = getEngine();
    try {
        const files = await fs_1.promises.readdir(partialsDir);
        for (const file of files) {
            if (file.endsWith('.hbs')) {
                const filePath = path_1.default.join(partialsDir, file);
                const content = await fs_1.promises.readFile(filePath, 'utf-8');
                const partialName = file.replace(/\.hbs$/, '');
                eng.registerPartial(partialName, content);
            }
        }
    }
    catch (error) {
        if (error.code !== 'ENOENT') {
            throw error;
        }
    }
}
async function loadTemplate(templateName, templateDir) {
    const templatePath = path_1.default.join(templateDir, `${templateName}.hbs`);
    try {
        return await fs_1.promises.readFile(templatePath, 'utf-8');
    }
    catch (error) {
        if (error.code === 'ENOENT') {
            // Try loading from layouts directory
            const layoutPath = path_1.default.join(templateDir, 'layouts', `${templateName}.hbs`);
            return await fs_1.promises.readFile(layoutPath, 'utf-8');
        }
        throw error;
    }
}
async function loadLayout(layoutName, templateDir) {
    const layoutPath = path_1.default.join(templateDir, 'layouts', `${layoutName}.hbs`);
    try {
        return await fs_1.promises.readFile(layoutPath, 'utf-8');
    }
    catch (error) {
        if (error.code === 'ENOENT') {
            // Return a default layout if the specified one doesn't exist
            return '{{body}}';
        }
        throw error;
    }
}
async function renderPage(pageHtml, templateContent, layoutName, pageData, templateDir) {
    const eng = getEngine();
    // Step 1: If a template is specified, render the page with the template
    let html = pageHtml;
    if (templateContent) {
        html = eng.render(templateContent, { ...pageData, body: pageHtml });
    }
    // Step 2: If a layout is specified, wrap with layout
    if (layoutName) {
        const layout = await loadLayout(layoutName, templateDir);
        html = eng.render(layout, { ...pageData, body: html });
    }
    return html;
}
//# sourceMappingURL=template.js.map