#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { build } from './generator';
import { serve } from './serve';

export function createCli(): Command {
  const program = new Command();

  program
    .name('ssg')
    .description('A static site generator for Markdown content');

  program
    .command('build')
    .description('Generate the static site')
    .option('--content <dir>', 'content directory to read Markdown files from', './content')
    .option('--output <dir>', 'output directory to write the generated site to', './dist')
    .option('--templates <dir>', 'templates directory containing layouts/ and partials/', './templates')
    .action((opts: { content: string; output: string; templates: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);
      const result = build({ contentDir, outputDir, templatesDir });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  program
    .command('serve')
    .description('Build the site, then serve it with live reload while watching for changes')
    .option('--content <dir>', 'content directory to read Markdown files from', './content')
    .option('--output <dir>', 'output directory to write the generated site to', './dist')
    .option('--templates <dir>', 'templates directory containing layouts/ and partials/', './templates')
    .option('--port <port>', 'port to serve the dev server on', '3000')
    .action(async (opts: { content: string; output: string; templates: string; port: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);
      const port = Number(opts.port);
      const handle = await serve({ contentDir, outputDir, templatesDir, port });
      // eslint-disable-next-line no-console
      console.log(`Dev server running at ${handle.url}`);
      // eslint-disable-next-line no-console
      console.log(`Watching ${opts.content} and ${opts.templates} for changes...`);
    });

  return program;
}

export function run(argv: string[]): void {
  createCli().parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
