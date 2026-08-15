import path from 'path';
import { readMarkdownFiles } from './files';
import { processMarkdownFile } from './page';
import { generatePageHtml, generateIndexHtml } from './generator';
import { PluginManager, PluginContext } from './plugin';
import { TemplatePlugin } from './plugins/template.plugin';
import { MarkdownPlugin } from './plugins/markdown.plugin';

export async function build(contentDir: string, outputDir: string, templateDir?: string, usePlugins = false): Promise<void> {
  console.log(`Reading markdown files from: ${contentDir}`);
  const files = await readMarkdownFiles(contentDir);

  if (files.length === 0) {
    console.log('No markdown files found.');
    return;
  }

  console.log(`Found ${files.length} markdown file(s).`);

  const context: PluginContext = { contentDir, outputDir, templateDir };
  const pluginManager = new PluginManager();

  if (usePlugins) {
    pluginManager.register(MarkdownPlugin);
    pluginManager.register(TemplatePlugin);
    await pluginManager.runOnStart(context);
    await pluginManager.runBeforeBuild(context);
  }

  const pages = [];
  for (const file of files) {
    const page = await processMarkdownFile(file.name, file.content);
    pages.push(page);
    await generatePageHtml(page, outputDir, templateDir, usePlugins ? pluginManager : undefined);
    console.log(`✓ Generated ${page.slug}.html`);
  }

  await generateIndexHtml(pages, outputDir);
  console.log(`✓ Generated index.html`);

  if (usePlugins) {
    await pluginManager.runAfterBuild(pages, context);
    await pluginManager.runOnEnd(context);
  }

  console.log(`\nBuild complete! Output: ${outputDir}`);
}
