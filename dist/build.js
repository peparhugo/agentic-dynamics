"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const files_1 = require("./files");
const page_1 = require("./page");
const generator_1 = require("./generator");
const plugin_1 = require("./plugin");
const template_plugin_1 = require("./plugins/template.plugin");
const markdown_plugin_1 = require("./plugins/markdown.plugin");
async function build(contentDir, outputDir, templateDir, usePlugins = false) {
    console.log(`Reading markdown files from: ${contentDir}`);
    const files = await (0, files_1.readMarkdownFiles)(contentDir);
    if (files.length === 0) {
        console.log('No markdown files found.');
        return;
    }
    console.log(`Found ${files.length} markdown file(s).`);
    const context = { contentDir, outputDir, templateDir };
    const pluginManager = new plugin_1.PluginManager();
    if (usePlugins) {
        pluginManager.register(markdown_plugin_1.MarkdownPlugin);
        pluginManager.register(template_plugin_1.TemplatePlugin);
        await pluginManager.runOnStart(context);
        await pluginManager.runBeforeBuild(context);
    }
    const pages = [];
    for (const file of files) {
        const page = await (0, page_1.processMarkdownFile)(file.name, file.content);
        pages.push(page);
        await (0, generator_1.generatePageHtml)(page, outputDir, templateDir, usePlugins ? pluginManager : undefined);
        console.log(`✓ Generated ${page.slug}.html`);
    }
    await (0, generator_1.generateIndexHtml)(pages, outputDir);
    console.log(`✓ Generated index.html`);
    if (usePlugins) {
        await pluginManager.runAfterBuild(pages, context);
        await pluginManager.runOnEnd(context);
    }
    console.log(`\nBuild complete! Output: ${outputDir}`);
}
//# sourceMappingURL=build.js.map