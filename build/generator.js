"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
const cache_1 = require("./cache");
function htmlEncode(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
function wrapPage(title, body) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${htmlEncode(title)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }
    a { color: #2563eb; }
    nav { margin-bottom: 2rem; }
    .meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .tag { background: #e5e7eb; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  ${body}
</body>
</html>`;
}
function renderPageHtml(page) {
    const { title, date, tags } = page.frontmatter;
    const metaParts = [];
    if (date)
        metaParts.push(`<time>${htmlEncode(date)}</time>`);
    const meta = metaParts.length
        ? `<div class="meta">${metaParts.join(' &middot; ')}</div>`
        : '';
    const tagsHtml = tags && tags.length > 0
        ? `<div class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join('\n')}</div>`
        : '';
    const body = `<article>
  <h1>${htmlEncode(title)}</h1>
  ${meta}
  ${tagsHtml}
  ${page.html}
</article>`;
    return wrapPage(title, body);
}
function renderIndexHtml(pages) {
    const items = pages
        .map((p) => {
        const { title, date, tags } = p.frontmatter;
        const tagsHtml = tags && tags.length > 0
            ? ` <span class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join(' ')}</span>`
            : '';
        const dateHtml = date ? ` <time>${htmlEncode(date)}</time>` : '';
        return `<li>
      <a href="${htmlEncode(p.slug)}.html">${htmlEncode(title)}</a>${dateHtml}${tagsHtml}
    </li>`;
    })
        .join('\n');
    const body = `<h1>All Posts</h1>
  <ul>
    ${items}
  </ul>`;
    return wrapPage('Index', body);
}
function registerPartials(partialsDir) {
    if (!fs_1.default.existsSync(partialsDir))
        return;
    const files = fs_1.default.readdirSync(partialsDir).filter((f) => f.endsWith('.hbs'));
    for (const file of files) {
        const name = path_1.default.basename(file, '.hbs');
        const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, file), 'utf-8');
        handlebars_1.default.registerPartial(name, content);
    }
}
function loadTemplates(templateDir) {
    if (!fs_1.default.existsSync(templateDir))
        return null;
    const partialsDir = path_1.default.join(templateDir, 'partials');
    registerPartials(partialsDir);
    const layoutsDir = path_1.default.join(templateDir, 'layouts');
    const layouts = new Map();
    if (fs_1.default.existsSync(layoutsDir)) {
        const files = fs_1.default.readdirSync(layoutsDir).filter((f) => f.endsWith('.hbs'));
        for (const file of files) {
            const name = path_1.default.basename(file, '.hbs');
            const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, file), 'utf-8');
            layouts.set(name, handlebars_1.default.compile(content));
        }
    }
    const pageTemplates = new Map();
    const files = fs_1.default.readdirSync(templateDir).filter((f) => f.endsWith('.hbs'));
    for (const file of files) {
        const name = path_1.default.basename(file, '.hbs');
        const content = fs_1.default.readFileSync(path_1.default.join(templateDir, file), 'utf-8');
        pageTemplates.set(name, handlebars_1.default.compile(content));
    }
    return {
        renderPage(page) {
            const templateName = page.frontmatter.template || 'page';
            const template = pageTemplates.get(templateName) || pageTemplates.get('page');
            if (!template) {
                throw new Error(`Page template "${templateName}" not found`);
            }
            const layoutName = page.frontmatter.layout || 'default';
            const layout = layouts.get(layoutName) || layouts.get('default');
            const body = template({
                title: page.frontmatter.title,
                date: page.frontmatter.date,
                tags: page.frontmatter.tags || [],
                content: page.html,
                slug: page.slug,
            });
            if (layout) {
                return layout({
                    title: page.frontmatter.title,
                    body,
                });
            }
            return body;
        },
        renderIndex(pages) {
            const hasIndex = pageTemplates.has('index');
            if (!hasIndex) {
                return renderIndexHtml(pages);
            }
            const template = pageTemplates.get('index');
            const layout = layouts.get('default');
            const body = template({
                pages: pages.map((p) => ({
                    title: p.frontmatter.title,
                    date: p.frontmatter.date,
                    tags: p.frontmatter.tags || [],
                    slug: p.slug,
                })),
            });
            if (layout) {
                return layout({ title: 'Index', body });
            }
            return body;
        },
    };
}
function generateSite(pages, outputDir, templateDir, cache, stats) {
    const engine = templateDir ? loadTemplates(templateDir) : null;
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const expectedFiles = new Set(pages.map((p) => `${p.slug}.html`));
    expectedFiles.add('index.html');
    const existingFiles = fs_1.default.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    for (const file of existingFiles) {
        if (!expectedFiles.has(file)) {
            fs_1.default.unlinkSync(path_1.default.join(outputDir, file));
        }
    }
    const currentTemplateHash = templateDir
        ? cache_1.BuildCache.computeTemplateHash(templateDir)
        : '';
    const cachePopulated = cache && cache.isPopulated();
    const cachedTemplateHash = cache ? cache.getTemplateHash() : '';
    for (const page of pages) {
        let html;
        const slug = page.slug;
        if (cachePopulated &&
            currentTemplateHash === cachedTemplateHash &&
            currentTemplateHash !== '' &&
            cache.getCachedPage(slug)) {
            html = cache.getCachedPage(slug).html;
            if (stats)
                stats.skipped++;
        }
        else {
            html = engine ? engine.renderPage(page) : renderPageHtml(page);
            if (stats)
                stats.built++;
            if (cache) {
                cache.setCachedPage(slug, { page, html });
            }
        }
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${slug}.html`), html, 'utf-8');
    }
    if (cache) {
        cache.setTemplateHash(currentTemplateHash);
    }
    const currentSlugs = pages.map((p) => p.slug).sort();
    const cachedSlugs = cache ? (cache.getIndexSlugs() || []).sort() : [];
    const slugsMatch = currentSlugs.length === cachedSlugs.length &&
        currentSlugs.every((s, i) => s === cachedSlugs[i]);
    if (cachePopulated &&
        currentTemplateHash === cachedTemplateHash &&
        currentTemplateHash !== '' &&
        slugsMatch &&
        cache.getIndexHtml()) {
        fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), cache.getIndexHtml(), 'utf-8');
    }
    else {
        const indexHtml = engine
            ? engine.renderIndex(pages)
            : renderIndexHtml(pages);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml, 'utf-8');
        if (cache) {
            cache.setIndexHtml(indexHtml);
            cache.setIndexSlugs(currentSlugs);
        }
    }
}
//# sourceMappingURL=generator.js.map