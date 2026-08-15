"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
exports.normalizeTemplateName = normalizeTemplateName;
exports.templateFingerprint = templateFingerprint;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
const hash_1 = require("./hash");
const LAYOUTS_DIR = 'layouts';
const PARTIALS_DIR = 'partials';
const DEFAULT_LAYOUT = 'default';
function listTemplateFiles(dir) {
    const files = [];
    if (!fs_1.default.existsSync(dir)) {
        return files;
    }
    for (const entry of fs_1.default.readdirSync(dir)) {
        const fullPath = path_1.default.join(dir, entry);
        const stat = fs_1.default.statSync(fullPath);
        if (stat.isDirectory()) {
            files.push(...listTemplateFiles(fullPath));
        }
        else if (stat.isFile() && /\.hbs$/i.test(entry)) {
            files.push(fullPath);
        }
    }
    return files;
}
function templateName(filePath, rootDir) {
    const relative = path_1.default.relative(rootDir, filePath);
    const withoutExtension = relative.replace(/\.hbs$/i, '');
    return withoutExtension.split(path_1.default.sep).join('/');
}
function normalizeTemplateName(name) {
    let normalized = name.trim();
    normalized = normalized.replace(/^\.?\//, '');
    normalized = normalized.replace(/^layouts\//, '');
    normalized = normalized.replace(/\.hbs$/i, '');
    return normalized.split(/[\\/]/).join('/');
}
/**
 * Computes a stable fingerprint for the template output a page resolves to.
 *
 * It hashes the resolved layout file (honouring the page's `template` name and
 * the `default` fallback) plus every registered partial. This mirrors the
 * resolution performed by {@link TemplateEngine.render} so the fingerprint only
 * changes when the actual rendered template would change.
 */
function templateFingerprint(templatesDir, requestedTemplate) {
    const parts = [];
    const layoutsDir = path_1.default.join(templatesDir, LAYOUTS_DIR);
    const layoutFiles = listTemplateFiles(layoutsDir);
    const candidates = [];
    if (requestedTemplate) {
        candidates.push(normalizeTemplateName(requestedTemplate));
    }
    candidates.push(DEFAULT_LAYOUT);
    let matched = false;
    for (const name of candidates) {
        const file = layoutFiles.find((candidate) => templateName(candidate, layoutsDir) === name);
        if (file) {
            parts.push(`layout:${name}:${(0, hash_1.hashFile)(file)}`);
            matched = true;
            break;
        }
    }
    // Partials only affect output when a layout is actually rendered; the
    // built-in fallback renderer ignores them.
    if (matched) {
        const partialsDir = path_1.default.join(templatesDir, PARTIALS_DIR);
        for (const file of listTemplateFiles(partialsDir)) {
            parts.push(`partial:${templateName(file, partialsDir)}:${(0, hash_1.hashFile)(file)}`);
        }
    }
    return (0, hash_1.hashString)(parts.join('\n'));
}
/**
 * A Handlebars-based template engine scoped to a single `templates` directory.
 *
 * It discovers layout templates from `templates/layouts/*.hbs` and reusable
 * partials from `templates/partials/*.hbs`. Each instance uses its own
 * isolated Handlebars environment so multiple builds never leak state.
 */
class TemplateEngine {
    constructor(templatesDir) {
        this.templatesDir = templatesDir;
        this.hbs = handlebars_1.default.create();
        this.layouts = new Map();
        this.defaultLayout = DEFAULT_LAYOUT;
        this.registerPartials();
        this.registerLayouts();
    }
    registerPartials() {
        const partialsDir = path_1.default.join(this.templatesDir, PARTIALS_DIR);
        for (const file of listTemplateFiles(partialsDir)) {
            const name = templateName(file, partialsDir);
            this.hbs.registerPartial(name, fs_1.default.readFileSync(file, 'utf-8'));
        }
    }
    registerLayouts() {
        const layoutsDir = path_1.default.join(this.templatesDir, LAYOUTS_DIR);
        for (const file of listTemplateFiles(layoutsDir)) {
            const name = templateName(file, layoutsDir);
            this.layouts.set(name, this.hbs.compile(fs_1.default.readFileSync(file, 'utf-8')));
        }
    }
    get availableLayouts() {
        return Array.from(this.layouts.keys());
    }
    hasLayout(name) {
        return this.layouts.has(normalizeTemplateName(name));
    }
    /**
     * Render a page using the requested layout (falling back to the default
     * layout). Returns `null` when no matching layout exists so the caller can
     * fall back to its built-in HTML rendering.
     */
    render(templateName, context) {
        const candidates = [];
        if (templateName) {
            candidates.push(normalizeTemplateName(templateName));
        }
        candidates.push(this.defaultLayout);
        for (const name of candidates) {
            const layout = this.layouts.get(name);
            if (layout) {
                return layout(context);
            }
        }
        return null;
    }
}
exports.TemplateEngine = TemplateEngine;
