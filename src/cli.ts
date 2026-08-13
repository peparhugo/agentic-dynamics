#!/usr/bin/env node

import { Command } from 'commander';
import { buildSite, startDevServer } from './index';

interface CliOptions {
  content: string;
  output: string;
  templates: string;
}

interface ServeCliOptions extends CliOptions {
  port: string;
}

function parsePort(value: string): number {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('port must be an integer between 1 and 65535');
  }
  return port;
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

program
  .command('serve')
  .description('build the site and start a live-reload development server')
  .option('--content <dir>', 'Markdown content directory', './content')
  .option('--output <dir>', 'generated site directory', './dist')
  .option('--templates <dir>', 'Handlebars template directory', './templates')
  .option('--port <number>', 'development server port', '3000')
  .action(async (options: ServeCliOptions) => {
    const server = await startDevServer({
      contentDir: options.content,
      outputDir: options.output,
      templatesDir: options.templates,
      port: parsePort(options.port)
    });
    process.stdout.write(`Development server running at http://localhost:${server.port}\n`);
  });

program.parseAsync().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Build failed: ${message}\n`);
  process.exitCode = 1;
});
