#!/usr/bin/env node
import { Command } from 'commander';
import { build } from './build';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator — converts Markdown files to HTML');

program
  .command('build')
  .description('Generate the site from Markdown files')
  .option('--content <dir>', 'Content directory containing Markdown files', './content')
  .option('--output <dir>', 'Output directory for generated HTML files', './dist')
  .action((options) => {
    try {
      build(options.content, options.output);
      console.log(`Site built successfully. Output: ${options.output}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(`Error: ${message}`);
      process.exit(1);
    }
  });

program.parse(process.argv);
