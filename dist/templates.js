"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = exports.DEFAULT_LAYOUT_SOURCE = exports.DEFAULT_TEMPLATE_SOURCE = exports.DEFAULT_LAYOUT_NAME = exports.DEFAULT_TEMPLATE_NAME = void 0;
exports.resolveFile = resolveFile;
exports.resolveTemplateFile = resolveTemplateFile;
exports.resolveLayoutFile = resolveLayoutFile;
exports.listPartialFiles = listPartialFiles;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
exports.DEFAULT_TEMPLATE_NAME = 'default';
exports.DEFAULT_LAYOUT_NAME = 'default';
exports.DEFAULT_TEMPLATE_SOURCE = '{{{body}}}';
exports.DEFAULT_LAYOUT_SOURCE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{title}}</title>
</head>
<body>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#if tags}}<ul class="tags">{{#each tags}}<li>{{this}}</li>{{/each}}</ul>{{/if}}
<div class="content">
{{{body}}}
</div>
</body>
</html>
`;
const TEMPLATE_EXTENSIONS = ['.hbs', '.handlebars'];
/**
 * Resolve a template/layout/partial name to a file path within `dir`. Names
 * may include an extension or omit it (in which case `.hbs`/`.handlebars` are
 * tried). Returns null when no matching file exists.
 */
function resolveFile(dir, name) {
    const candidates = [];
    if (path_1.default.extname(name)) {
        candidates.push(name);
    }
    else {
        for (const ext of TEMPLATE_EXTENSIONS) {
            candidates.push(name + ext);
        }
    }
    for (const candidate of candidates) {
        const full = path_1.default.join(dir, candidate);
        if (fs_1.default.existsSync(full) && fs_1.default.statSync(full).isFile()) {
            return full;
        }
    }
    return null;
}
function resolveTemplateFile(templatesDir, name, defaultName) {
    const resolved = name && name.length > 0 ? name : defaultName;
    return resolveFile(templatesDir, resolved);
}
function resolveLayoutFile(layoutsDir, name, defaultName) {
    const resolved = name && name.length > 0 ? name : defaultName;
    return resolveFile(layoutsDir, resolved);
}
function listPartialFiles(partialsDir) {
    if (!fs_1.default.existsSync(partialsDir)) {
        return [];
    }
    return fs_1.default
        .readdirSync(partialsDir, { withFileTypes: true })
        .filter((entry) => entry.isFile() && TEMPLATE_EXTENSIONS.includes(path_1.default.extname(entry.name)))
        .map((entry) => path_1.default.join(partialsDir, entry.name));
}
class TemplateEngine {
    constructor(templatesDir, options = {}) {
        this.templatesDir = path_1.default.resolve(templatesDir);
        this.layoutsDir = path_1.default.join(this.templatesDir, 'layouts');
        this.partialsDir = path_1.default.join(this.templatesDir, 'partials');
        this.defaultTemplate = options.defaultTemplate ?? exports.DEFAULT_TEMPLATE_NAME;
        this.defaultLayout = options.defaultLayout ?? exports.DEFAULT_LAYOUT_NAME;
        this.handlebars = handlebars_1.default.create();
        this.compiled = new Map();
        this.registerPartials();
    }
    /**
     * Render a page: apply the page template (produces the body) and then wrap
     * the result with the layout template via the {{{body}}} placeholder.
     */
    render(templateName, layoutName, context) {
        const templateSource = this.resolveTemplate(templateName);
        const body = this.compile(templateSource)({
            ...context,
            body: context.content,
        });
        if (layoutName === false) {
            return body;
        }
        const layoutSource = this.resolveLayout(layoutName);
        return this.compile(layoutSource)({ ...context, body });
    }
    resolveTemplate(name) {
        const file = resolveTemplateFile(this.templatesDir, name, this.defaultTemplate);
        if (file) {
            return fs_1.default.readFileSync(file, 'utf8');
        }
        return exports.DEFAULT_TEMPLATE_SOURCE;
    }
    resolveLayout(name) {
        const file = resolveLayoutFile(this.layoutsDir, name, this.defaultLayout);
        if (file) {
            return fs_1.default.readFileSync(file, 'utf8');
        }
        return exports.DEFAULT_LAYOUT_SOURCE;
    }
    compile(source) {
        const cached = this.compiled.get(source);
        if (cached) {
            return cached;
        }
        const fn = this.handlebars.compile(source);
        this.compiled.set(source, fn);
        return fn;
    }
    registerPartials() {
        for (const file of listPartialFiles(this.partialsDir)) {
            const ext = path_1.default.extname(file);
            const name = path_1.default.basename(file, ext);
            const source = fs_1.default.readFileSync(file, 'utf8');
            this.handlebars.registerPartial(name, source);
        }
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=templates.js.map