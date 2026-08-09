#!/usr/bin/env node
import { Command } from 'commander';
import path from 'path';
import { buildSite } from './build';
import { serveWithLiveReload } from './server';

const program = new Command();

program
  .name('ssg')
  .description('Static site generator (Markdown + Handlebars)')
  .version('0.1.0');

function addCommonOptions(cmd: Command) {
  return cmd
    .requiredOption('-s, --src <dir>', 'Source directory of Markdown files')
    .requiredOption('-t, --templates <dir>', 'Templates directory (Handlebars: layouts, pages, partials)')
    .requiredOption('-o, --out <dir>', 'Output directory for generated site')
    .option('--include-drafts', 'Include draft posts', false)
    .option('--site-title <title>', 'Site title for templates and RSS')
    .option('--site-url <url>', 'Absolute site URL (e.g. https://example.com) for RSS and absolute links')
    .option('--base-url <base>', 'Base URL path prefix (e.g. /blog)');
}

addCommonOptions(program.command('build').description('Build the site'))
  .action(async (opts) => {
    const options = {
      srcDir: path.resolve(opts.src),
      templatesDir: path.resolve(opts.templates),
      outDir: path.resolve(opts.out),
      includeDrafts: !!opts.includeDrafts,
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      baseUrl: opts.baseUrl,
    };
    await buildSite(options);
  });

addCommonOptions(program.command('serve').description('Start dev server with live reload'))
  .option('-p, --port <port>', 'Port to serve', (v) => parseInt(v, 10), 5173)
  .action(async (opts) => {
    const options = {
      srcDir: path.resolve(opts.src),
      templatesDir: path.resolve(opts.templates),
      outDir: path.resolve(opts.out),
      includeDrafts: !!opts.includeDrafts,
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      baseUrl: opts.baseUrl,
      port: opts.port,
    };
    await serveWithLiveReload(options);
  });

// Default to build if no subcommand
addCommonOptions(program)
  .allowExcessArguments(false)
  .action(async (opts) => {
    const options = {
      srcDir: path.resolve(opts.src),
      templatesDir: path.resolve(opts.templates),
      outDir: path.resolve(opts.out),
      includeDrafts: !!opts.includeDrafts,
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      baseUrl: opts.baseUrl,
    };
    await buildSite(options);
  });

program.parseAsync(process.argv);
