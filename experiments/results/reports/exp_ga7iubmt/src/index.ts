#!/usr/bin/env node
import { Command } from 'commander';
import { build } from './generator.js';
import { serve } from './server.js';
import { BuildOptions, ServeOptions } from './types.js';

export function createProgram(): Command {
  const program = new Command();

  program
    .name('ssg')
    .description('Static site generator with Markdown + Handlebars')
    .version('1.0.0');

  program
    .command('build')
    .description('Build the static site')
    .option('-s, --source <dir>', 'source directory of markdown files', './content')
    .option('-t, --templates <dir>', 'templates directory', './templates')
    .option('-o, --output <dir>', 'output directory', './dist')
    .option('--title <title>', 'site title')
    .option('--description <desc>', 'site description')
    .option('--url <url>', 'site base URL')
    .option('--include-drafts', 'include draft posts')
    .action(async (opts: BuildOptions) => {
      try {
        await build(opts);
        console.log('Site built successfully.');
      } catch (err) {
        console.error('Build failed:', err);
        process.exit(1);
      }
    });

  program
    .command('serve')
    .description('Start dev server with live reload')
    .option('-s, --source <dir>', 'source directory of markdown files', './content')
    .option('-t, --templates <dir>', 'templates directory', './templates')
    .option('-o, --output <dir>', 'output directory', './dist')
    .option('-p, --port <number>', 'port to listen on', '3000')
    .option('--title <title>', 'site title')
    .option('--description <desc>', 'site description')
    .option('--url <url>', 'site base URL')
    .action(async (opts: ServeOptions) => {
      try {
        await serve(opts);
      } catch (err) {
        console.error('Server failed:', err);
        process.exit(1);
      }
    });

  return program;
}

if (!process.env.VITEST) {
  createProgram().parse();
}
