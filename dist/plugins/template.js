"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
exports.renderPage = renderPage;
exports.renderIndex = renderIndex;
const templates_1 = require("../templates");
function renderPage(page) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.title}</title>
${page.tags.length ? `  <meta name="keywords" content="${page.tags.join(', ')}">` : ''}
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${page.title}</h1>
${page.date ? `      <time>${page.date}</time>` : ''}
      <div>${page.content}</div>
    </article>
  </main>
</body>
</html>`;
}
function renderIndex(pages) {
    const listItems = pages
        .map((page) => {
        const dateStr = page.date ? ` <time>${page.date}</time>` : '';
        const tagsStr = page.tags.length ? ` [${page.tags.join(', ')}]` : '';
        return `      <li><a href="${page.slug}.html">${page.title}</a>${dateStr}${tagsStr}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Pages</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
${listItems}
    </ul>
  </main>
</body>
</html>`;
}
class TemplatePlugin {
    constructor() {
        this.name = 'template';
        this.engine = null;
    }
    beforeBuild(options) {
        this.templatesDir = options.templatesDir;
        this.engine = options.templatesDir ? new templates_1.TemplateEngine(options.templatesDir) : null;
    }
    onFile(page) {
        return page;
    }
    render(page) {
        if (!this.engine || !this.engine.initialized)
            return null;
        return this.engine.render(page);
    }
    renderIndex(pages) {
        if (!this.engine || !this.engine.initialized)
            return null;
        return this.engine.renderIndex(pages);
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template.js.map