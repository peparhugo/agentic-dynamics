#!/usr/bin/env node
import { Command } from 'commander';
import { createEngine } from './index';
import { startDevelopmentServer } from './server';
import type { Page } from './types';

const program = new Command()
  .name('ssg')
  .description('Generate a static site from Markdown files');

program
  .command('build')
  .description('Generate the site')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .option('--templates <dir>', 'templates directory', './templates')
  .option('--incremental', 'only rebuild changed pages')
  .option('--clean', 'ignore the build cache and perform a clean build')
  .action(async (options: { content: string; output: string; templates: string; incremental?: boolean; clean?: boolean }) => {
    const engine = await createEngine(options);
    let pages: Page[];
    try {
      pages = await engine.build();
    } finally {
      await engine.end();
    }
    const { pagesBuilt, pagesSkipped, durationMs, timeSavedMs } = engine.stats;
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${pathForDisplay(options.output)}\n`);
    process.stdout.write(`Build stats: ${pagesBuilt} built, ${pagesSkipped} skipped, ${Math.round(durationMs)}ms elapsed, ${Math.round(timeSavedMs)}ms saved\n`);
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
