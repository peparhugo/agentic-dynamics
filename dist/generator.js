import * as fs from 'fs';
import * as path from 'path';
import { PluginManager } from './plugin-manager.js';
import { MarkdownPlugin } from './plugins/markdown-plugin.js';
import { TemplatePlugin } from './plugins/template-plugin.js';
export class SiteGenerator {
    constructor(options, plugins) {
        this.contentDir = options.contentDir;
        this.outputDir = options.outputDir;
        this.templatesDir = options.templatesDir || './templates';
        const defaultPlugins = [new MarkdownPlugin(), new TemplatePlugin()];
        const allPlugins = plugins ? [...defaultPlugins, ...plugins] : defaultPlugins;
        this.pluginManager = new PluginManager(allPlugins);
    }
    ensureDir(dirPath) {
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
        }
    }
    getMarkdownFiles() {
        if (!fs.existsSync(this.contentDir)) {
            return [];
        }
        return fs
            .readdirSync(this.contentDir)
            .filter((file) => file.endsWith('.md'))
            .sort();
    }
    generateIndexHtml(pages) {
        const pagesList = pages
            .map((page) => `    <li>
      <a href="${this.escapeHtml(page.url)}">${this.escapeHtml(page.title)}</a>
      ${page.date ? `<span style="color: #666; margin-left: 10px;">${this.escapeHtml(page.date)}</span>` : ''}
      ${page.tags.length > 0 ? `<div style="margin-top: 5px;"><small>${page.tags.map((tag) => `<span style="display: inline-block; background: #eee; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">${this.escapeHtml(tag)}</span>`).join('')}</small></div>` : ''}
    </li>`)
            .join('\n');
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Static Site</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    h1 { margin-top: 0; }
    ul { list-style: none; padding: 0; }
    li {
      padding: 15px;
      border: 1px solid #eee;
      margin-bottom: 10px;
      border-radius: 5px;
    }
    li:hover { background: #f9f9f9; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  ${pages.length > 0 ? `<ul>\n${pagesList}\n  </ul>` : '<p>No pages found.</p>'}
</body>
</html>`;
    }
    escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    getPluginManager() {
        return this.pluginManager;
    }
    async build() {
        this.ensureDir(this.outputDir);
        const pluginContext = {
            contentDir: this.contentDir,
            outputDir: this.outputDir,
            templatesDir: this.templatesDir,
        };
        await this.pluginManager.onStart(pluginContext);
        await this.pluginManager.beforeBuild(pluginContext);
        const markdownFiles = this.getMarkdownFiles();
        const pages = [];
        for (const file of markdownFiles) {
            const filePath = path.join(this.contentDir, file);
            const content = fs.readFileSync(filePath, 'utf-8');
            const fileContext = {
                filename: file,
                filePath,
                content,
            };
            await this.pluginManager.onFile(pluginContext, fileContext);
            if (fileContext.html && fileContext.pageMetadata) {
                const outputPath = path.join(this.outputDir, fileContext.pageMetadata.url);
                fs.writeFileSync(outputPath, fileContext.html);
                pages.push(fileContext.pageMetadata);
            }
        }
        const indexPath = path.join(this.outputDir, 'index.html');
        fs.writeFileSync(indexPath, this.generateIndexHtml(pages));
        await this.pluginManager.afterBuild(pluginContext, pages);
        await this.pluginManager.onEnd(pluginContext);
        console.log(`✓ Generated ${pages.length} page(s) to ${this.outputDir}`);
    }
}
//# sourceMappingURL=generator.js.map