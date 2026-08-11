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
exports.build = build;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const template_1 = require("./template");
const template_engine_1 = require("./template-engine");
function normalizeDate(d) {
    if (d instanceof Date)
        return d.toISOString().slice(0, 10);
    if (typeof d === 'string')
        return d;
    return undefined;
}
function normalizeTags(t) {
    if (Array.isArray(t))
        return t.map((v) => String(v));
    return undefined;
}
function normalizeVal(v) {
    if (typeof v === 'string')
        return v;
    return undefined;
}
function build(contentDir, outputDir, templatesDir) {
    const absoluteContent = path.resolve(contentDir);
    if (!fs.existsSync(absoluteContent)) {
        throw new Error(`Content directory does not exist: ${absoluteContent}`);
    }
    let engine;
    if (templatesDir && fs.existsSync(templatesDir)) {
        engine = new template_engine_1.TemplateEngine({ templatesDir: path.resolve(templatesDir) });
    }
    const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));
    const pages = [];
    for (const file of files) {
        const filePath = path.join(absoluteContent, file);
        const slug = path.basename(file, '.md');
        const raw = gray_matter_1.default.read(filePath);
        const html = marked_1.marked.parse(raw.content);
        const page = {
            slug,
            title: String(raw.data.title || slug),
            date: normalizeDate(raw.data.date),
            tags: normalizeTags(raw.data.tags),
            template: normalizeVal(raw.data.template),
            layout: normalizeVal(raw.data.layout),
            content: raw.content,
            html,
        };
        pages.push(page);
    }
    pages.sort((a, b) => {
        if (a.date && b.date) {
            return b.date.localeCompare(a.date);
        }
        if (a.date)
            return -1;
        if (b.date)
            return 1;
        return a.title.localeCompare(b.title);
    });
    const absoluteOutput = path.resolve(outputDir);
    if (!fs.existsSync(absoluteOutput)) {
        fs.mkdirSync(absoluteOutput, { recursive: true });
    }
    for (const page of pages) {
        let html;
        if (engine) {
            const tplName = page.template || (engine.hasTemplate('default') ? 'default' : undefined);
            const lytName = page.layout || (engine.hasLayout('default') ? 'default' : undefined);
            html = engine.render(page, tplName, lytName);
        }
        else {
            html = (0, template_1.pageTemplate)(page);
        }
        fs.writeFileSync(path.join(absoluteOutput, `${page.slug}.html`), html);
    }
    let indexHtml;
    if (engine && engine.hasIndex()) {
        indexHtml = engine.renderIndex(pages);
    }
    else {
        indexHtml = (0, template_1.indexTemplate)(pages);
    }
    fs.writeFileSync(path.join(absoluteOutput, 'index.html'), indexHtml);
}
//# sourceMappingURL=build.js.map