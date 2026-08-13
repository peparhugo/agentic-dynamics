#!/usr/bin/env node

import { Command } from 'commander';
import { buildSite } from './index';

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
    .action(async (options: { content: string; output: string; templates: string }) => {
      const pages = await buildSite({ contentDir: options.content, outputDir: options.output, templateDir: options.templates });
      process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${pathForMessage(options.output)}\n`);
    });

  return program;
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
