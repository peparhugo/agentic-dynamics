#!/usr/bin/env node
import { Command } from 'commander';
import path from 'path';
import fs from 'fs';
import { buildSite } from './builder';
import { startDevServer } from './server';

export async function run(argv: string[]) {
  const program = new Command();
  program
    .name('ssg')
    .description('Static site generator (TS)')
    .option('-s, --src <dir>', 'Source directory of Markdown files', 'content')
    .option('-t, --templates <dir>', 'Handlebars templates directory', 'templates')
    .option('-o, --out <dir>', 'Output directory', 'public')
    .option('--site-title <title>', 'Site title', 'Site')
    .option('--site-url <url>', 'Site URL (for RSS)')
    .option('--serve', 'Start dev server with live reload')
    .option('--port <port>', 'Dev server port', (v) => parseInt(v, 10), 5173)
    .action(async (opts) => {
      const srcDir = path.resolve(opts.src);
      const templatesDir = path.resolve(opts.templates);
      const outDir = path.resolve(opts.out);
      for (const d of [srcDir, templatesDir]) {
        if (!fs.existsSync(d)) {
          throw new Error(`Directory not found: ${d}`);
        }
      }
      if (opts.serve) {
        await startDevServer({ srcDir, templatesDir, outDir, siteTitle: opts.siteTitle, siteUrl: opts.siteUrl, dev: true, port: opts.port });
      } else {
        await buildSite({ srcDir, templatesDir, outDir, siteTitle: opts.siteTitle, siteUrl: opts.siteUrl, dev: false });
      }
    });

  await program.parseAsync(argv);
}

if (require.main === module) {
  run(process.argv).catch((err) => {
    // eslint-disable-next-line no-console
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
