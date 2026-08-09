#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './build.js';
import { startDevServer } from './server.js';
import { DEFAULT_CONFIG, type SiteConfig } from './types.js';

interface CommonOptions {
  source: string;
  templates: string;
  out: string;
  baseUrl: string;
  title: string;
  description: string;
  drafts: boolean;
  clean: boolean;
}

export function configFromOptions(opts: CommonOptions): SiteConfig {
  return {
    sourceDir: opts.source,
    templateDir: opts.templates,
    outputDir: opts.out,
    baseUrl: opts.baseUrl,
    title: opts.title,
    description: opts.description,
    includeDrafts: opts.drafts,
    clean: opts.clean,
  };
}

function addCommonOptions(cmd: Command): Command {
  return cmd
    .option('-s, --source <dir>', 'source directory of markdown files', DEFAULT_CONFIG.sourceDir)
    .option('-t, --templates <dir>', 'directory of Handlebars templates', DEFAULT_CONFIG.templateDir)
    .option('-o, --out <dir>', 'output directory', DEFAULT_CONFIG.outputDir)
    .option('--base-url <url>', 'absolute base URL for RSS/links', DEFAULT_CONFIG.baseUrl)
    .option('--title <title>', 'site title', DEFAULT_CONFIG.title)
    .option('--description <text>', 'site description', DEFAULT_CONFIG.description)
    .option('--drafts', 'include pages marked draft: true', false)
    .option('--clean', 'remove the output directory before building', false);
}

export function createProgram(): Command {
  const program = new Command();
  program
    .name('ssgen')
    .description('Static site generator: Markdown + YAML frontmatter + Handlebars')
    .version('1.0.0');

  addCommonOptions(
    program
      .command('build')
      .description('Build the site once and exit'),
  ).action((opts: CommonOptions) => {
    const config = configFromOptions(opts);
    const result = buildSite(config);
    console.log(
      `[ssgen] wrote ${result.outputFiles.length} files ` +
        `(${result.pages.length} pages, ${result.tagPages.length} tag pages, ` +
        `${result.assets.length} assets) to ${config.outputDir}`,
    );
  });

  addCommonOptions(
    program
      .command('serve')
      .description('Build, watch, and serve with live reload')
      .option('-p, --port <port>', 'port to listen on', '3000'),
  ).action(async (opts: CommonOptions & { port: string }) => {
    const config = configFromOptions(opts);
    await startDevServer(config, Number(opts.port));
  });

  return program;
}

const isMain = process.argv[1]?.endsWith('cli.ts') || process.argv[1]?.endsWith('cli.js');
if (isMain) {
  createProgram().parseAsync(process.argv).catch((err) => {
    console.error('[ssgen]', err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
