#!/usr/bin/env node
import { Command } from 'commander';
import path from 'node:path';
import { generateSite } from './generator';
import { startDevServer } from './server';

export type CliOptions = {
  src: string;
  templates: string;
  out: string;
  drafts?: boolean;
  siteUrl?: string;
  watch?: boolean;
  port?: number;
};

export function parseCliArgs(argv: string[]): CliOptions {
  const program = new Command();
  program
    .name('ts-ssg')
    .description('A TypeScript static site generator with Handlebars and live reload dev server')
    .option('-s, --src <dir>', 'Source directory of Markdown files', 'content')
    .option('-t, --templates <dir>', 'Templates directory with Handlebars files', 'templates')
    .option('-o, --out <dir>', 'Output directory', 'public')
    .option('-d, --drafts', 'Include drafts', false)
    .option('--site-url <url>', 'Site base URL for RSS links')
    .option('-w, --watch', 'Start dev server with live reload', false)
    .option('-p, --port <number>', 'Dev server port', (v) => parseInt(v, 10), 5173);

  program.parse(argv);
  const opts = program.opts();
  return {
    src: path.resolve(opts.src),
    templates: path.resolve(opts.templates),
    out: path.resolve(opts.out),
    drafts: !!opts.drafts,
    siteUrl: opts.siteUrl,
    watch: !!opts.watch,
    port: opts.port
  };
}

async function main() {
  const opts = parseCliArgs(process.argv);
  if (opts.watch) {
    await startDevServer({
      srcDir: opts.src,
      templatesDir: opts.templates,
      outDir: opts.out,
      includeDrafts: opts.drafts,
      siteUrl: opts.siteUrl,
      port: opts.port || 5173,
      devInjectReload: true
    });
  } else {
    await generateSite({
      srcDir: opts.src,
      templatesDir: opts.templates,
      outDir: opts.out,
      includeDrafts: opts.drafts,
      siteUrl: opts.siteUrl,
      devInjectReload: false
    });
  }
}

// Only run when invoked directly
if (require.main === module) {
  // eslint-disable-next-line unicorn/prefer-top-level-await
  main().catch((err) => {
    // eslint-disable-next-line no-console
    console.error(err);
    process.exit(1);
  });
}
