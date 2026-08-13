#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './index';

const program = new Command()
  .name('ssg')
  .description('Generate a static site from Markdown files');

program
  .command('build')
  .description('Generate the site')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .action(async (options: { content: string; output: string }) => {
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${pathForDisplay(options.output)}\n`);
  });

function pathForDisplay(value: string): string {
  return value.replace(/[\\/]$/, '') || value;
}

program.parseAsync().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Error: ${message}\n`);
  process.exitCode = 1;
});
