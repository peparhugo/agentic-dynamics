#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { buildSite } from './generator';

export function run(argv: string[]): void {
  const program = new Command();

  program.name('ssg').description('A static site generator').version('1.0.0');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .action((opts: { content: string; output: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const result = buildSite({ contentDir, outputDir });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  program.parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
