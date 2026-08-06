#!/usr/bin/env node
import { Command } from 'commander';
import path from 'node:path';
import { buildSite } from './generator.js';
import { startDevServer } from './server.js';

export async function runCli(argv: string[]) {
  const program = new Command();
  program
    .name('ts-ssg')
    .description('Static site generator (TypeScript)')
    .version('0.1.0');

  function commonOptions(cmd: Command) {
    return cmd
      .requiredOption('-s, --source <dir>', 'Source directory of Markdown files')
      .requiredOption('-t, --templates <dir>', 'Templates directory (Handlebars)')
      .requiredOption('-o, --out <dir>', 'Output directory for generated site')
      .option('--base-url <url>', 'Base URL for RSS and absolute links')
      .option('--site-title <title>', 'Site title for RSS', 'Site')
      .option('--include-drafts', 'Include draft posts', false)
      .option('--clean', 'Clean output directory before build', false);
  }

  commonOptions(program.command('build').description('Build the static site')).action(async (opts) => {
    await buildSite({
      sourceDir: path.resolve(opts.source),
      templatesDir: path.resolve(opts.templates),
      outDir: path.resolve(opts.out),
      baseUrl: opts.baseUrl,
      siteTitle: opts.siteTitle,
      includeDrafts: !!opts.includeDrafts,
      clean: !!opts.clean,
    });
  });

  commonOptions(program.command('dev').description('Start dev server with live reload'))
    .option('-p, --port <port>', 'Dev server port', (v) => parseInt(v, 10), 5173)
    .action(async (opts) => {
      await startDevServer({
        sourceDir: path.resolve(opts.source),
        templatesDir: path.resolve(opts.templates),
        outDir: path.resolve(opts.out),
        baseUrl: opts.baseUrl,
        siteTitle: opts.siteTitle,
        includeDrafts: !!opts.includeDrafts,
        clean: !!opts.clean,
        port: opts.port,
        watch: true,
      });
    });

  await program.parseAsync(argv);
}

// If executed directly, run with process.argv
if (import.meta.url === `file://${process.argv[1]}`) {
  runCli(process.argv).catch((err) => {
    // eslint-disable-next-line no-console
    console.error(err);
    process.exit(1);
  });
}
