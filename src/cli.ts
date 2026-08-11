#!/usr/bin/env node

import { Command } from 'commander';
import { buildSite } from './generator';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator')
  .version('1.0.0');

program
  .command('build')
  .description('Build the static site')
  .option('--content <dir>', 'Content directory', './content')
  .option('--output <dir>', 'Output directory', './dist')
  .option('--templates <dir>', 'Templates directory', './templates')
  .action((options) => {
    try {
      buildSite(options.content, options.output, options.templates);
      console.log(`Site built successfully in ${options.output}`);
    } catch (err) {
      console.error('Error:', (err as Error).message);
      process.exit(1);
    }
  });

program.parse(process.argv);
