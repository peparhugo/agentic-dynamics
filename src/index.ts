#!/usr/bin/env node
import { Command } from 'commander';
import path from 'path';
import { build } from './build';

const program = new Command();

program
  .name('ssg')
  .description('A static site generator')
  .version('1.0.0');

program
  .command('build')
  .description('Build the static site')
  .option('--content <dir>', 'Content directory', './content')
  .option('--output <dir>', 'Output directory', './dist')
  .action((options) => {
    const contentDir = path.resolve(options.content);
    const outputDir = path.resolve(options.output);
    build({ contentDir, outputDir });
  });

program.parse(process.argv);
