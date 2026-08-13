#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { startDevServer } from './devServer';
import { buildSite } from './generator';

export function run(argv: string[]): void {
  const program = new Command();

  program.name('ssg').description('A static site generator').version('1.0.0');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .action((opts: { content: string; output: string; templates: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);
      const result = buildSite({ contentDir, outputDir, templatesDir });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  program
    .command('serve')
    .description('Build the site and serve it with live reload')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .option('--port <port>', 'port to serve on', '3000')
    .action(async (opts: { content: string; output: string; templates: string; port: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);
      const port = parseInt(opts.port, 10);
      const server = await startDevServer({ contentDir, outputDir, templatesDir, port });
      // eslint-disable-next-line no-console
      console.log(`Serving ${outputDir} at http://localhost:${server.port} (watching ${opts.content}, ${opts.templates})`);
    });

  program.parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
