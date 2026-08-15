#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './site';

export function run(argv: string[]): void {
  const program = new Command();

  program.name('ssg').description('A static site generator CLI');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .action((opts: { content: string; output: string }) => {
      const result = buildSite({ contentDir: opts.content, outputDir: opts.output });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  program.parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
