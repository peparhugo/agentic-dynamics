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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadTemplates = loadTemplates;
exports.renderPageTemplate = renderPageTemplate;
exports.renderIndexTemplate = renderIndexTemplate;
const fs_1 = require("fs");
const path = __importStar(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
const TEMPLATE_EXTENSIONS = ['.hbs'];
const DEFAULT_TEMPLATE_NAME = 'default';
const DEFAULT_LAYOUT_NAME = 'default';
const INDEX_TEMPLATE_NAME = 'index';
async function dirExists(dir) {
    try {
        const stat = await fs_1.promises.stat(dir);
        return stat.isDirectory();
    }
    catch {
        return false;
    }
}
async function readTemplateMap(dir, hbs) {
    const map = new Map();
    if (!(await dirExists(dir))) {
        return map;
    }
    const entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
        if (!entry.isFile()) {
            continue;
        }
        const ext = path.extname(entry.name).toLowerCase();
        if (!TEMPLATE_EXTENSIONS.includes(ext)) {
            continue;
        }
        const name = entry.name.slice(0, -ext.length);
        const source = await fs_1.promises.readFile(path.join(dir, entry.name), 'utf8');
        map.set(name, hbs.compile(source));
    }
    return map;
}
/**
 * Load the template tree at `templatesDir`.
 *
 * Expected layout:
 *   ./templates/            page templates (.hbs)
 *   ./templates/layouts/    layout templates (.hbs)
 *   ./templates/partials/   reusable partials (.hbs)
 *
 * `default.hbs` is used when a page does not name a template and
 * `layouts/default.hbs` wraps every rendered page unless the page opts out
 * via a `layout:` frontmatter field.
 */
async function loadTemplates(templatesDir) {
    const exists = await dirExists(templatesDir);
    if (!exists) {
        return {
            exists: false,
            hbs: handlebars_1.default.create(),
            templates: new Map(),
            layouts: new Map(),
            partials: new Map(),
            defaultTemplate: null,
            defaultLayout: null,
            hasIndexTemplate: false,
        };
    }
    const hbs = handlebars_1.default.create();
    const templates = await readTemplateMap(templatesDir, hbs);
    const layouts = await readTemplateMap(path.join(templatesDir, 'layouts'), hbs);
    const partials = await readTemplateMap(path.join(templatesDir, 'partials'), hbs);
    for (const [name, template] of partials) {
        hbs.registerPartial(name, template);
    }
    return {
        exists: true,
        hbs,
        templates,
        layouts,
        partials,
        defaultTemplate: templates.has(DEFAULT_TEMPLATE_NAME) ? DEFAULT_TEMPLATE_NAME : null,
        defaultLayout: layouts.has(DEFAULT_LAYOUT_NAME) ? DEFAULT_LAYOUT_NAME : null,
        hasIndexTemplate: templates.has(INDEX_TEMPLATE_NAME),
    };
}
function normalizeTemplateName(value) {
    let name = value.trim().replace(/\\/g, '/').split('/').pop() || '';
    for (const ext of TEMPLATE_EXTENSIONS) {
        if (name.toLowerCase().endsWith(ext)) {
            name = name.slice(0, -ext.length);
            break;
        }
    }
    return name;
}
function makePageContext(page) {
    return {
        page,
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        content: page.content,
        html: page.html,
        ...page.data,
    };
}
function resolveLayoutName(page, bundle) {
    if (page.layout) {
        return normalizeTemplateName(page.layout);
    }
    return bundle.defaultLayout;
}
/**
 * Render a single page through its template and layout. Throws when a page
 * explicitly names a template or layout that cannot be found.
 */
function renderPageTemplate(page, bundle) {
    if (!bundle.exists) {
        throw new Error('templates directory not found');
    }
    let templateName = bundle.defaultTemplate;
    if (page.template) {
        templateName = normalizeTemplateName(page.template);
    }
    const template = templateName ? bundle.templates.get(templateName) : undefined;
    if (!template) {
        throw new Error(`template not found: ${templateName}`);
    }
    const context = makePageContext(page);
    const body = template(context);
    const layoutName = resolveLayoutName(page, bundle);
    const layout = layoutName ? bundle.layouts.get(layoutName) : undefined;
    if (layoutName && !layout) {
        throw new Error(`layout not found: ${layoutName}`);
    }
    if (layout) {
        return layout({ ...context, body });
    }
    return body;
}
/**
 * Render the site index from `index.hbs` when present, otherwise return null
 * so callers can fall back to the built-in index renderer.
 */
function renderIndexTemplate(pages, bundle) {
    if (!bundle.exists || !bundle.hasIndexTemplate) {
        return null;
    }
    const template = bundle.templates.get(INDEX_TEMPLATE_NAME);
    if (!template) {
        return null;
    }
    const context = { pages, site: { pages } };
    const body = template(context);
    const layoutName = bundle.defaultLayout;
    const layout = layoutName ? bundle.layouts.get(layoutName) : undefined;
    if (layout) {
        return layout({ ...context, body });
    }
    return body;
}
