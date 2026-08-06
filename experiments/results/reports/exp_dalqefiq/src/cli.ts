#!/usr/bin/env node
import { Command } from 'commander';
import path from 'node:path';
import { buildSite } from './build';
import { startDevServer } from './server';

const program = new Command();
program
  .name('ssg')
  .description('Fast static site generator (throughput-optimized)')
  .version('0.1.0');

program
  .command('build')
  .description('Build the static site')
  .requiredOption('-s, --src <dir>', 'Source directory of Markdown files')
  .requiredOption('-t, --templates <dir>', 'Templates directory (Handlebars)')
  .requiredOption('-o, --out <dir>', 'Output directory for generated site')
  .option('--base-url <url>', 'Base URL of the site (for RSS)')
  .option('--drafts', 'Include drafts', false)
  .option('--concurrency <n>', 'Max parallelism', (v: string) => parseInt(v, 10))
  .option('--clean', 'Clean output directory before build', false)
  .action(async (opts) => {
    const options = {
      srcDir: path.resolve(String(opts.src)),
      templatesDir: path.resolve(String(opts.templates)),
      outDir: path.resolve(String(opts.out)),
      baseUrl: opts.baseUrl ? String(opts.baseUrl) : undefined,
      includeDrafts: Boolean(opts.drafts),
      concurrency: Number.isFinite(opts.concurrency) ? Number(opts.concurrency) : undefined,
      clean: Boolean(opts.clean),
      liveReload: false
    };
    await buildSite(options);
    // eslint-disable-next-line no-console
    console.log('Build complete.');
  });

program
  .command('serve')
  .description('Start dev server with live reload and watch')
  .requiredOption('-s, --src <dir>', 'Source directory of Markdown files')
  .requiredOption('-t, --templates <dir>', 'Templates directory (Handlebars)')
  .requiredOption('-o, --out <dir>', 'Output directory for generated site')
  .option('--base-url <url>', 'Base URL of the site (for RSS)')
  .option('--drafts', 'Include drafts', true)
  .option('--concurrency <n>', 'Max parallelism', (v: string) => parseInt(v, 10))
  .option('--clean', 'Clean output directory before first build', false)
  .option('-p, --port <n>', 'Port', (v: string) => parseInt(v, 10), 5173)
  .action(async (opts) => {
    const options = {
      srcDir: path.resolve(String(opts.src)),
      templatesDir: path.resolve(String(opts.templates)),
      outDir: path.resolve(String(opts.out)),
      baseUrl: opts.baseUrl ? String(opts.baseUrl) : undefined,
      includeDrafts: Boolean(opts.drafts),
      concurrency: Number.isFinite(opts.concurrency) ? Number(opts.concurrency) : undefined,
      clean: Boolean(opts.clean),
      liveReload: true,
      port: Number(opts.port)
    } as const;
    const { url } = await startDevServer(options as any);
    // eslint-disable-next-line no-console
    console.log(`Dev server running at ${url}`);
  });

program.parseAsync(process.argv);
