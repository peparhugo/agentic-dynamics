#!/usr/bin/env node
import { Command } from 'commander';
import path from 'path';
import { build } from './build';
import { serve } from './serve';

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
  .option('--templates <dir>', 'Templates directory')
  .action((options) => {
    const contentDir = path.resolve(options.content);
    const outputDir = path.resolve(options.output);
    const templatesDir = options.templates ? path.resolve(options.templates) : undefined;
    build({ contentDir, outputDir, templatesDir });
  });

program
  .command('serve')
  .description('Start a live-reload development server')
  .option('--content <dir>', 'Content directory', './content')
  .option('--output <dir>', 'Output directory', './dist')
  .option('--templates <dir>', 'Templates directory')
  .option('--port <number>', 'Port to listen on', '3000')
  .action((options) => {
    const contentDir = path.resolve(options.content);
    const outputDir = path.resolve(options.output);
    const templatesDir = options.templates ? path.resolve(options.templates) : undefined;
    const port = parseInt(options.port, 10);
    const instance = serve({ contentDir, outputDir, templatesDir, port });
    instance.ready.then(() => {
      console.log(`Dev server running at http://localhost:${port}`);
    });
  });

program.parse(process.argv);
