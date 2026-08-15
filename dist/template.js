import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
export class TemplateEngine {
    constructor(options) {
        this.cache = new Map();
        this.templatesDir = options.templatesDir;
        this.layoutsDir = options.layoutsDir;
        this.partialsDir = options.partialsDir;
        this.registerPartials();
    }
    registerPartials() {
        if (!fs.existsSync(this.partialsDir)) {
            return;
        }
        const files = fs.readdirSync(this.partialsDir).filter(file => file.endsWith('.hbs'));
        for (const file of files) {
            const filePath = path.join(this.partialsDir, file);
            const content = fs.readFileSync(filePath, 'utf-8');
            const partialName = file.replace(/\.hbs$/, '');
            Handlebars.registerPartial(partialName, content);
        }
    }
    getTemplate(filename) {
        if (this.cache.has(filename)) {
            return this.cache.get(filename);
        }
        const filePath = path.join(this.templatesDir, filename);
        if (!fs.existsSync(filePath)) {
            throw new Error(`Template not found: ${filename}`);
        }
        const content = fs.readFileSync(filePath, 'utf-8');
        const template = Handlebars.compile(content);
        this.cache.set(filename, template);
        return template;
    }
    getLayout(layoutName) {
        return this.getTemplate(`layouts/${layoutName}`);
    }
    render(templateName, layoutName, data) {
        const template = this.getTemplate(templateName);
        const renderedContent = template(data);
        if (!layoutName) {
            return renderedContent;
        }
        const layout = this.getLayout(layoutName);
        return layout({
            ...data,
            body: renderedContent
        });
    }
    renderWithLayout(content, layoutName, data) {
        if (!layoutName) {
            return content;
        }
        const layout = this.getLayout(layoutName);
        return layout({
            ...data,
            body: content
        });
    }
}
export function createDefaultLayout() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    .date { color: #666; font-size: 0.9em; }
    .tags { margin: 10px 0; }
    .tag { display: inline-block; background: #f0f0f0; padding: 2px 8px; margin: 2px; border-radius: 3px; font-size: 0.9em; }
    nav { border-bottom: 1px solid #ddd; margin-bottom: 20px; padding-bottom: 10px; }
  </style>
</head>
<body>
  {{>nav}}
  <article>
    <h1>{{title}}</h1>
    {{#if date}}<p class="date">{{date}}</p>{{/if}}
    {{#if tags}}<div class="tags">{{#each tags}}<span class="tag">{{this}}</span>{{/each}}</div>{{/if}}
    <div class="content">
      {{{body}}}
    </div>
  </article>
</body>
</html>`;
}
export function createDefaultIndexLayout() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    li { margin: 8px 0; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  <ul>
    {{#each pages}}<li><a href="{{slug}}.html">{{title}}{{#if date}} ({{date}}){{/if}}</a></li>{{/each}}
  </ul>
</body>
</html>`;
}
export function createDefaultNavPartial() {
    return `<nav>
    <a href="index.html">← Home</a>
  </nav>`;
}
//# sourceMappingURL=template.js.map