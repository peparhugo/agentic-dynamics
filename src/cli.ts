#!/usr/bin/env node

import { Command } from 'commander';
import { buildSite } from './index';

interface CliOptions {
  content: string;
  output: string;
  templates: string;
}

const program = new Command();

program
  .name('ssg')
  .description('Generate a static HTML site from Markdown files')
  .command('build')
  .description('generate the site')
  .option('--content <dir>', 'Markdown content directory', './content')
  .option('--output <dir>', 'generated site directory', './dist')
  .option('--templates <dir>', 'Handlebars template directory', './templates')
  .action(async (options: CliOptions) => {
    const pages = await buildSite({
      contentDir: options.content,
      outputDir: options.output,
      templatesDir: options.templates
    });
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${options.output}\n`);
  });

program.parseAsync().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Build failed: ${message}\n`);
  process.exitCode = 1;
});
