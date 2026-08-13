#!/usr/bin/env node

import { Command } from 'commander';
import { buildSite } from './index';
import { startDevServer } from './server';
import type { BuildStats } from './types';

export function createProgram(): Command {
  const program = new Command();
  program
    .name('ssg')
    .description('Generate a static HTML site from Markdown files')
    .showHelpAfterError();

  program
    .command('build')
    .description('Generate the site')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'template directory', './templates')
    .option('--incremental', 'only rebuild changed pages')
    .option('--clean', 'force a clean build')
    .action(async (options: { content: string; output: string; templates: string; incremental?: boolean; clean?: boolean }) => {
      let stats: BuildStats | undefined;
      const pages = await buildSite({
        contentDir: options.content,
        outputDir: options.output,
        templateDir: options.templates,
        incremental: options.incremental,
        clean: options.clean,
        onStats: (result) => { stats = result; },
      });
      if (options.incremental && stats) {
        process.stdout.write(`Built ${stats.pagesBuilt} page${stats.pagesBuilt === 1 ? '' : 's'}, skipped ${stats.pagesSkipped} in ${stats.durationMs}ms (saved ${stats.timeSavedMs}ms)\n`);
      } else {
        process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${pathForMessage(options.output)}\n`);
      }
    });

  program
    .command('serve')
    .description('Build and serve the site with live reload')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'template directory', './templates')
    .option('--port <number>', 'server port', parsePort, 3000)
    .action(async (options: { content: string; output: string; templates: string; port: number }) => {
      const server = await startDevServer({
        contentDir: options.content,
        outputDir: options.output,
        templateDir: options.templates,
        port: options.port,
      });
      process.stdout.write(`Serving ${pathForMessage(options.output)} at http://${server.host}:${server.port}\n`);
    });

  return program;
}

function parsePort(value: string): number {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Port must be an integer between 1 and 65535: ${value}`);
  }
  return port;
}

function pathForMessage(output: string): string {
  return output.replace(/[\\/]$/, '') || output;
}

if (require.main === module) {
  createProgram().parseAsync(process.argv).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
