#!/usr/bin/env node

import { Command } from 'commander';
import { resolve } from 'path';
import { generate } from './generator';
import { startDevServer } from './server';
import { SiteConfig } from './types';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator')
  .version('1.0.0')
  .option('-s, --source <dir>', 'source directory of markdown files', 'source')
  .option('-o, --output <dir>', 'output directory for generated HTML', 'dist')
  .option(
    '-t, --templates <dir>',
    'templates directory for Handlebars templates',
    'templates',
  )
  .option('-S, --serve', 'start dev server with live reload')
  .option('-p, --port <number>', 'dev server port', '3000')
  .option('--site-title <title>', 'site title', 'My Static Site')
  .option('--site-url <url>', 'site URL for RSS', 'http://localhost:3000')
  .action((opts) => {
    const config: SiteConfig = {
      source: resolve(process.cwd(), opts.source),
      output: resolve(process.cwd(), opts.output),
      templates: resolve(process.cwd(), opts.templates),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      devPort: parseInt(opts.port, 10) || 3000,
    };

    if (opts.serve) {
      generate(config, { silent: true, isDev: true });
      startDevServer(config);
    } else {
      generate(config);
    }
  });

program.parse();
