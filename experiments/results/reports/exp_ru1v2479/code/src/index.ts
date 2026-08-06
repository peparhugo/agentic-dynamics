#!/usr/bin/env node
import { Command } from 'commander';
import { SiteConfig } from './types';
import { generate } from './generator';
import { startServer } from './server';

const program = new Command();

program
  .name('staticsite')
  .description('Static site generator from Markdown with YAML frontmatter')
  .version('1.0.0');

program
  .command('build')
  .description('Build the static site')
  .requiredOption('-s, --source <dir>', 'Source directory of Markdown files', 'content')
  .requiredOption('-t, --templates <dir>', 'Template directory', 'templates')
  .requiredOption('-o, --output <dir>', 'Output directory', 'public')
  .option('--title <title>', 'Site title', 'My Site')
  .option('--url <url>', 'Site URL', 'http://localhost:3000')
  .option('--drafts', 'Include draft posts', false)
  .option('--posts-per-page <n>', 'Posts per page', '10')
  .action((opts) => {
    const config: SiteConfig = {
      sourceDir: opts.source,
      templateDir: opts.templates,
      outputDir: opts.output,
      siteTitle: opts.title,
      siteUrl: opts.url,
      includeDrafts: opts.drafts,
      postsPerPage: parseInt(opts.postsPerPage, 10),
      port: 3000,
    };
    generate(config);
    console.log(`[staticsite] site built to ${config.outputDir}`);
  });

program
  .command('serve')
  .description('Start dev server with live reload')
  .requiredOption('-s, --source <dir>', 'Source directory of Markdown files', 'content')
  .requiredOption('-t, --templates <dir>', 'Template directory', 'templates')
  .requiredOption('-o, --output <dir>', 'Output directory', 'public')
  .option('--title <title>', 'Site title', 'My Site')
  .option('--url <url>', 'Site URL', 'http://localhost:3000')
  .option('--drafts', 'Include draft posts', false)
  .option('-p, --port <port>', 'Dev server port', '3000')
  .option('--posts-per-page <n>', 'Posts per page', '10')
  .action((opts) => {
    const config: SiteConfig = {
      sourceDir: opts.source,
      templateDir: opts.templates,
      outputDir: opts.output,
      siteTitle: opts.title,
      siteUrl: `http://localhost:${opts.port}`,
      includeDrafts: opts.drafts,
      postsPerPage: parseInt(opts.postsPerPage, 10),
      port: parseInt(opts.port, 10),
    };
    startServer(config);
  });

program.parse();
