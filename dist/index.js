"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getMarkdownFiles = getMarkdownFiles;
exports.parseMarkdownFile = parseMarkdownFile;
exports.generatePageHtml = generatePageHtml;
exports.generateIndexHtml = generateIndexHtml;
exports.build = build;
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const js_yaml_1 = __importDefault(require("js-yaml"));
const markdown_it_1 = __importDefault(require("markdown-it"));
const template_engine_1 = require("./template-engine");
const md = new markdown_it_1.default();
const matterOptions = {
    engines: {
        yaml: {
            parse: (input) => js_yaml_1.default.load(input, { schema: js_yaml_1.default.FAILSAFE_SCHEMA }),
        },
    },
};
async function walkDir(dir, baseDir, results) {
    const entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    const sortedEntries = entries
        .filter((e) => e.isFile() && e.name.endsWith(".md"))
        .sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of sortedEntries) {
        results.push(path_1.default.relative(baseDir, path_1.default.join(dir, entry.name)));
    }
    const subdirs = entries
        .filter((e) => e.isDirectory())
        .sort((a, b) => a.name.localeCompare(b.name));
    for (const subdir of subdirs) {
        await walkDir(path_1.default.join(dir, subdir.name), baseDir, results);
    }
    return results;
}
async function getMarkdownFiles(contentDir) {
    const absDir = path_1.default.resolve(contentDir);
    try {
        await fs_1.promises.access(absDir);
    }
    catch {
        throw new Error(`Content directory not found: ${absDir}`);
    }
    const files = [];
    await walkDir(absDir, absDir, files);
    return files.sort();
}
async function parseMarkdownFile(contentDir, filePath) {
    const absPath = path_1.default.join(contentDir, filePath);
    const raw = await fs_1.promises.readFile(absPath, "utf-8");
    const { data, content } = (0, gray_matter_1.default)(raw, matterOptions);
    const html = md.render(content);
    const frontmatter = {};
    for (const [key, value] of Object.entries(data)) {
        frontmatter[key] = String(value ?? "");
    }
    return { path: filePath, frontmatter, html };
}
function generatePageHtml(page) {
    let title = page.frontmatter.title || page.path;
    const date = page.frontmatter.date
        ? `<p class="date">${page.frontmatter.date}</p>`
        : "";
    const tags = page.frontmatter.tags
        ? `<p class="tags">Tags: ${page.frontmatter.tags}</p>`
        : "";
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
</head>
<body>
${date}
${tags}
${page.html}
</body>
</html>`;
}
function generateIndexHtml(pages) {
    const items = pages
        .map((page) => {
        const href = page.path.replace(/\.md$/, ".html");
        const title = page.frontmatter.title || page.path;
        const date = page.frontmatter.date
            ? `<span class="date">${page.frontmatter.date}</span>`
            : "";
        const tags = page.frontmatter.tags
            ? `<span class="tags">Tags: ${page.frontmatter.tags}</span>`
            : "";
        return `    <li>
      <a href="${href}">${title}</a>
      ${date}
      ${tags}
    </li>`;
    })
        .join("\n");
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Site Index</title>
</head>
<body>
<h1>Pages</h1>
<ul>
${items}
</ul>
</body>
</html>`;
}
async function build(options) {
    const contentDir = path_1.default.resolve(options.contentDir);
    const outputDir = path_1.default.resolve(options.outputDir);
    const templatesDir = options.templatesDir
        ? path_1.default.resolve(options.templatesDir)
        : path_1.default.resolve("templates");
    const engine = await (0, template_engine_1.createTemplateEngine)(templatesDir);
    await fs_1.promises.mkdir(outputDir, { recursive: true });
    const files = await getMarkdownFiles(contentDir);
    const pages = [];
    for (const file of files) {
        const page = await parseMarkdownFile(contentDir, file);
        pages.push(page);
        const outPath = file.replace(/\.md$/, ".html");
        const fullOutPath = path_1.default.join(outputDir, outPath);
        const outDir = path_1.default.dirname(fullOutPath);
        await fs_1.promises.mkdir(outDir, { recursive: true });
        let pageHtml;
        if (engine) {
            pageHtml = engine.renderPage(page.frontmatter, page.html);
        }
        else {
            pageHtml = generatePageHtml(page);
        }
        await fs_1.promises.writeFile(fullOutPath, pageHtml, "utf-8");
    }
    let indexHtml;
    if (engine) {
        indexHtml = engine.renderIndex(pages);
        if (!indexHtml) {
            indexHtml = generateIndexHtml(pages);
        }
    }
    else {
        indexHtml = generateIndexHtml(pages);
    }
    await fs_1.promises.writeFile(path_1.default.join(outputDir, "index.html"), indexHtml, "utf-8");
}
