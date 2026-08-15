#!/usr/bin/env node

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import path from 'path';
import { build } from './build';
import { serve } from './serve';

export { build } from './build';

yargs(hideBin(process.argv))
  .command(
    'build',
    'Build the static site',
    (yargs) => {
      return yargs
        .option('content', {
          alias: 'c',
          describe: 'Content directory',
          type: 'string',
          default: './content'
        })
        .option('output', {
          alias: 'o',
          describe: 'Output directory',
          type: 'string',
          default: './dist'
        })
        .option('templates', {
          alias: 't',
          describe: 'Templates directory',
          type: 'string'
        })
        .option('incremental', {
          describe: 'Only rebuild changed pages',
          type: 'boolean',
          default: false
        })
        .option('clean', {
          describe: 'Clear cache before building',
          type: 'boolean',
          default: false
        });
    },
    async (argv) => {
      const contentDir = path.resolve(argv.content as string);
      const outputDir = path.resolve(argv.output as string);
      const templateDir = argv.templates ? path.resolve(argv.templates as string) : undefined;
      const incremental = argv.incremental as boolean;
      const clean = argv.clean as boolean;

      try {
        await build(contentDir, outputDir, templateDir, false, { incremental, clean });
      } catch (error) {
        console.error('Error:', (error as Error).message);
        process.exit(1);
      }
    }
  )
  .command(
    'serve',
    'Start a live-reload dev server',
    (yargs) => {
      return yargs
        .option('content', {
          alias: 'c',
          describe: 'Content directory',
          type: 'string',
          default: './content'
        })
        .option('output', {
          alias: 'o',
          describe: 'Output directory',
          type: 'string',
          default: './dist'
        })
        .option('templates', {
          alias: 't',
          describe: 'Templates directory',
          type: 'string'
        })
        .option('port', {
          alias: 'p',
          describe: 'Port to serve on',
          type: 'number',
          default: 3000
        });
    },
    async (argv) => {
      const contentDir = path.resolve(argv.content as string);
      const outputDir = path.resolve(argv.output as string);
      const templateDir = argv.templates ? path.resolve(argv.templates as string) : undefined;
      const port = argv.port as number;

      try {
        console.log('Building initial site...');
        await build(contentDir, outputDir, templateDir);
        console.log('\n');
        await serve(outputDir, contentDir, templateDir, port);
      } catch (error) {
        console.error('Error:', (error as Error).message);
        process.exit(1);
      }
    }
  )
  .demandCommand()
  .strict()
  .help()
  .parse();
