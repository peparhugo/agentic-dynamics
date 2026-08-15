#!/usr/bin/env node
import path from 'path';
import { Command } from 'commander';
import { build } from './build';

const program = new Command();

program.name('ssg').description('A minimal static site generator');

program
  .command('build')
  .description('Generate the static site')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .action((opts: { content: string; output: string }) => {
    const contentDir = path.resolve(process.cwd(), opts.content);
    const outputDir = path.resolve(process.cwd(), opts.output);
    const result = build({ contentDir, outputDir });
    console.log(`Built ${result.pages.length} page(s) into ${outputDir}`);
  });

if (require.main === module) {
  program.parse(process.argv);
}

export { program };
