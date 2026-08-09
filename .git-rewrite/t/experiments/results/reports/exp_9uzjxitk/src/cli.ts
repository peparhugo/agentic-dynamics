#!/usr/bin/env node
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { generate } from './generator.js';
import { startDevServer } from './server.js';
import type { SiteConfig } from './types.js';

yargs(hideBin(process.argv))
  .scriptName('ssg')
  .command(
    'build',
    'Generate static HTML site',
    (y) =>
      y
        .option('src', { type: 'string', default: 'content', describe: 'Source directory of Markdown files' })
        .option('templates', { type: 'string', default: 'templates', describe: 'Template directory' })
        .option('output', { type: 'string', default: 'public', describe: 'Output directory' })
        .option('base-url', { type: 'string', default: 'http://localhost:8080', describe: 'Base URL for RSS and links' })
        .option('site-title', { type: 'string', default: 'My Site', describe: 'Site title' })
        .option('site-description', { type: 'string', default: 'A static site', describe: 'Site description' }),
    async (argv) => {
      const config: SiteConfig = {
        src: argv.src,
        templates: argv.templates,
        output: argv.output,
        baseUrl: argv['base-url'],
        siteTitle: argv['site-title'],
        siteDescription: argv['site-description'],
      };
      generate(config);
      console.log(`Site built to ${config.output}`);
    },
  )
  .command(
    'serve',
    'Start dev server with live reload',
    (y) =>
      y
        .option('src', { type: 'string', default: 'content', describe: 'Source directory of Markdown files' })
        .option('templates', { type: 'string', default: 'templates', describe: 'Template directory' })
        .option('output', { type: 'string', default: 'public', describe: 'Output directory' })
        .option('base-url', { type: 'string', default: 'http://localhost:8080', describe: 'Base URL' })
        .option('site-title', { type: 'string', default: 'My Site', describe: 'Site title' })
        .option('site-description', { type: 'string', default: 'A static site', describe: 'Site description' })
        .option('port', { type: 'number', default: 8080, describe: 'Dev server port' }),
    async (argv) => {
      const config: SiteConfig = {
        src: argv.src,
        templates: argv.templates,
        output: argv.output,
        baseUrl: argv['base-url'],
        siteTitle: argv['site-title'],
        siteDescription: argv['site-description'],
      };
      startDevServer(config, argv.port);
    },
  )
  .demandCommand(1, 'You need at least one command before moving on')
  .strict()
  .help()
  .parse();
