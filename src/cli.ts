#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './index';
import { startDevelopmentServer } from './server';

const program = new Command()
  .name('ssg')
  .description('Generate a static site from Markdown files');

program
  .command('build')
  .description('Generate the site')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .option('--templates <dir>', 'templates directory', './templates')
  .action(async (options: { content: string; output: string; templates: string }) => {
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${pathForDisplay(options.output)}\n`);
  });

program
  .command('serve')
  .description('Build and serve the site with live reload')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .option('--templates <dir>', 'templates directory', './templates')
  .option('--port <number>', 'server port', (value: string) => {
    const port = Number(value);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
    return port;
  }, 3000)
  .action(async (options: { content: string; output: string; templates: string; port: number }) => {
    const server = await startDevelopmentServer(options);
    process.stdout.write(`Serving ${pathForDisplay(options.output)} at http://localhost:${server.port}\n`);
  });

function pathForDisplay(value: string): string {
  return value.replace(/[\\/]$/, '') || value;
}

program.parseAsync().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Error: ${message}\n`);
  process.exitCode = 1;
});
