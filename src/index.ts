#!/usr/bin/env node
import { Command } from 'commander';
import { build } from './build';
import { serve } from './serve';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator — converts Markdown files to HTML');

program
  .command('build')
  .description('Generate the site from Markdown files')
  .option('--content <dir>', 'Content directory containing Markdown files', './content')
  .option('--output <dir>', 'Output directory for generated HTML files', './dist')
  .option('--templates <dir>', 'Templates directory for Handlebars layouts, templates, and partials', './templates')
  .option('--incremental', 'Only rebuild changed pages using cache', false)
  .option('--clean', 'Force a clean build, ignoring any existing cache', false)
  .action((options) => {
    try {
      build(options.content, options.output, options.templates, {
        incremental: options.incremental,
        clean: options.clean,
      });
      console.log(`Site built successfully. Output: ${options.output}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(`Error: ${message}`);
      process.exit(1);
    }
  });

program
  .command('serve')
  .description('Start a development server with live reload')
  .option('--content <dir>', 'Content directory containing Markdown files', './content')
  .option('--output <dir>', 'Output directory for generated HTML files', './dist')
  .option('--templates <dir>', 'Templates directory for Handlebars layouts, templates, and partials', './templates')
  .option('--port <port>', 'Port to listen on', '3000')
  .action((options) => {
    serve({
      content: options.content,
      output: options.output,
      templates: options.templates,
      port: parseInt(options.port, 10),
    });
  });

program.parse(process.argv);
