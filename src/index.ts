#!/usr/bin/env node

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { build } from './ssg';

yargs(hideBin(process.argv))
  .scriptName('ssg')
  .command(
    'build',
    'Build the static site',
    (yargs) =>
      yargs
        .option('content', {
          type: 'string',
          default: './content',
          describe: 'Content directory with Markdown files',
        })
        .option('output', {
          type: 'string',
          default: './dist',
          describe: 'Output directory for generated HTML',
        }),
    (argv) => {
      build({
        contentDir: argv.content as string,
        outputDir: argv.output as string,
      });
    }
  )
  .demandCommand(1, 'Please specify a command: build')
  .help()
  .parse();
