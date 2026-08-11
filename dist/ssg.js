"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const template_engine_1 = require("./template-engine");
function slugify(filename) {
    const name = path_1.default.basename(filename, path_1.default.extname(filename));
    return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}
function readMarkdownFiles(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        return [];
    }
    return fs_1.default.readdirSync(contentDir)
        .filter(f => f.endsWith('.md'))
        .map(f => path_1.default.join(contentDir, f));
}
function parsePage(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    const html = marked_1.marked.parse(content);
    const slug = slugify(path_1.default.basename(filePath));
    return {
        frontmatter: {
            title: data.title || slug,
            date: data.date,
            tags: data.tags,
            template: data.template,
            layout: data.layout,
        },
        html,
        slug,
    };
}
function toTemplateData(page) {
    const { title, date, tags } = page.frontmatter;
    return {
        title,
        date,
        dateFormatted: date ? new Date(date).toLocaleDateString('en-US') : undefined,
        tags,
        tagsStr: tags && tags.length > 0 ? tags.join(', ') : undefined,
        content: page.html,
        slug: page.slug,
    };
}
function build(options) {
    const { contentDir, outputDir, templateDir } = options;
    if (!fs_1.default.existsSync(outputDir)) {
        fs_1.default.mkdirSync(outputDir, { recursive: true });
    }
    const engine = new template_engine_1.TemplateEngine(templateDir);
    const files = readMarkdownFiles(contentDir);
    const pages = [];
    for (const file of files) {
        const page = parsePage(file);
        pages.push(page);
        const data = toTemplateData(page);
        const pageHTML = engine.renderPage(data, page.frontmatter.template, page.frontmatter.layout);
        const outPath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, pageHTML, 'utf-8');
    }
    const indexData = {
        title: 'My Static Site',
        pages: pages.map(toTemplateData),
    };
    const indexHTML = engine.renderIndex(indexData);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHTML, 'utf-8');
}
//# sourceMappingURL=ssg.js.map