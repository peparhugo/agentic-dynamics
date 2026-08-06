#!/usr/bin/env node
import { Command } from 'commander';
import { parseMarkdownFiles } from './parser.js';
import { generateSite } from './generator.js';
import { startDevServer } from './server.js';
import type { SiteConfig } from './types.js';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator from Markdown and Handlebars templates')
  .version('1.0.0')
  .requiredOption('-s, --source <dir>', 'Source directory of markdown files')
  .requiredOption('-t, --templates <dir>', 'Template directory')
  .requiredOption('-o, --output <dir>', 'Output directory')
  .option('--site-title <title>', 'Site title')
  .option('--site-url <url>', 'Site URL (enables RSS feed generation)')
  .option('--site-description <desc>', 'Site description')
  .option('--serve', 'Start dev server with live reload')
  .option('-p, --port <port>', 'Dev server port', '3000')
  .action(async (options) => {
    const config: SiteConfig = {
      sourceDir: options.source,
      templateDir: options.templates,
      outputDir: options.output,
      siteTitle: options.siteTitle,
      siteUrl: options.siteUrl,
      siteDescription: options.siteDescription,
    };

    const build = async () => {
      const pages = await parseMarkdownFiles(config.sourceDir);
      await generateSite(pages, config);
      console.log(`Built ${pages.length} pages to ${config.outputDir}`);
    };

    await build();

    if (options.serve) {
      await startDevServer(config, parseInt(options.port, 10), build);
    }
  });

program.parse();
