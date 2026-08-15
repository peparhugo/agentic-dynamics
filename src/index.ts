#!/usr/bin/env node

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import path from 'path';
import { readMarkdownFiles } from './files';
import { processMarkdownFile } from './page';
import { generatePageHtml, generateIndexHtml } from './generator';
import { serve } from './serve';

async function build(contentDir: string, outputDir: string, templateDir?: string): Promise<void> {
  console.log(`Reading markdown files from: ${contentDir}`);
  const files = await readMarkdownFiles(contentDir);

  if (files.length === 0) {
    console.log('No markdown files found.');
    return;
  }

  console.log(`Found ${files.length} markdown file(s).`);

  const pages = [];
  for (const file of files) {
    const page = await processMarkdownFile(file.name, file.content);
    pages.push(page);
    await generatePageHtml(page, outputDir, templateDir);
    console.log(`✓ Generated ${page.slug}.html`);
  }

  await generateIndexHtml(pages, outputDir);
  console.log(`✓ Generated index.html`);

  console.log(`\nBuild complete! Output: ${outputDir}`);
}

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
        });
    },
    async (argv) => {
      const contentDir = path.resolve(argv.content as string);
      const outputDir = path.resolve(argv.output as string);
      const templateDir = argv.templates ? path.resolve(argv.templates as string) : undefined;

      try {
        await build(contentDir, outputDir, templateDir);
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
