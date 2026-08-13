#!/usr/bin/env node
import { Command } from 'commander';
import { build } from './build';

export function createProgram(): Command {
  const program = new Command();

  program.name('ssg').description('A static site generator').version('1.0.0');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .action((opts: { content: string; output: string }) => {
      const result = build({ contentDir: opts.content, outputDir: opts.output });
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  return program;
}

if (require.main === module) {
  createProgram().parse(process.argv);
}
