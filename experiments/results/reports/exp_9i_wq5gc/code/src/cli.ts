#!/usr/bin/env node
import path from 'node:path';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { buildSite } from './builder';
import { startDevServer } from './server';

export async function runCli(argv: string[]) {
  return yargs(argv)
    .scriptName('ssg')
    .command(
      'build',
      'Build the static site',
      (y) =>
        y
          .option('src', { type: 'string', demandOption: true, describe: 'Source directory of Markdown files' })
          .option('templates', { type: 'string', demandOption: true, describe: 'Handlebars templates directory' })
          .option('out', { type: 'string', demandOption: true, describe: 'Output directory for HTML' })
          .option('baseUrl', { type: 'string', describe: 'Base URL for RSS absolute links (e.g., https://example.com/)' })
          .option('include-drafts', { type: 'boolean', default: false, describe: 'Include draft posts' })
          .option('clean', { type: 'boolean', default: true, describe: 'Clean output directory before build' })
          .option('watch', { type: 'boolean', default: false, describe: 'Watch for changes and rebuild' })
          .option('serve', { type: 'boolean', default: false, describe: 'Serve the output with live reload' })
          .option('port', { type: 'number', default: 5173, describe: 'Dev server port' }),
      async (args) => {
        const srcDir = path.resolve(String(args.src));
        const templatesDir = path.resolve(String(args.templates));
        const outDir = path.resolve(String(args.out));
        const includeDrafts = !!args['include-drafts'];
        const cleanOutDir = !!args.clean;
        const baseUrl = args.baseUrl ? String(args.baseUrl) : undefined;
        if (args.watch || args.serve) {
          await startDevServer({ srcDir, templatesDir, outDir, includeDrafts, baseUrl, cleanOutDir, devServerPort: Number(args.port), watch: !!args.watch });
        } else {
          await buildSite({ srcDir, templatesDir, outDir, includeDrafts, baseUrl, cleanOutDir });
        }
      }
    )
    .command(
      'dev',
      'Start dev server (watch + serve)',
      (y) =>
        y
          .option('src', { type: 'string', demandOption: true, describe: 'Source directory of Markdown files' })
          .option('templates', { type: 'string', demandOption: true, describe: 'Handlebars templates directory' })
          .option('out', { type: 'string', demandOption: true, describe: 'Output directory for HTML' })
          .option('baseUrl', { type: 'string', describe: 'Base URL for RSS absolute links (e.g., https://example.com/)' })
          .option('include-drafts', { type: 'boolean', default: true, describe: 'Include draft posts in dev' })
          .option('port', { type: 'number', default: 5173, describe: 'Dev server port' }),
      async (args) => {
        const srcDir = path.resolve(String(args.src));
        const templatesDir = path.resolve(String(args.templates));
        const outDir = path.resolve(String(args.out));
        const includeDrafts = !!args['include-drafts'];
        const baseUrl = args.baseUrl ? String(args.baseUrl) : undefined;
        await startDevServer({ srcDir, templatesDir, outDir, includeDrafts, baseUrl, cleanOutDir: true, devServerPort: Number(args.port), watch: true });
      }
    )
    .demandCommand(1)
    .help()
    .parseAsync();
}

if (require.main === module) {
  runCli(hideBin(process.argv));
}
