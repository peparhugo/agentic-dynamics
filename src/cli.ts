#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { build } from './generator';

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
    .action((opts: { content: string; output: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const result = build({ contentDir, outputDir });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  return program;
}

export function run(argv: string[]): void {
  createCli().parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
