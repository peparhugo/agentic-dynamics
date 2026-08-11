#!/usr/bin/env node

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { build } from './ssg';
import { serve } from './serve';

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
        })
        .option('templates', {
          type: 'string',
          default: './templates',
          describe: 'Template directory',
        }),
    (argv) => {
      build({
        contentDir: argv.content as string,
        outputDir: argv.output as string,
        templateDir: argv.templates as string,
      });
    }
  )
  .command(
    'serve',
    'Start dev server with live reload',
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
        })
        .option('templates', {
          type: 'string',
          default: './templates',
          describe: 'Template directory',
        })
        .option('port', {
          type: 'number',
          default: 3000,
          describe: 'Port to listen on',
        }),
    (argv) => {
      serve({
        contentDir: argv.content as string,
        outputDir: argv.output as string,
        templateDir: argv.templates as string,
        port: argv.port as number,
      });
    }
  )
  .demandCommand(1, 'Please specify a command: build or serve')
  .help()
  .parse();
