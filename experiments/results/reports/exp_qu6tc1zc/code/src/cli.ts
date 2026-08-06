#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './build.js';
import { startDevServer } from './server.js';
import { DEFAULT_CONFIG, type SiteConfig } from './types.js';

interface CommonOpts {
  source: string;
  templates: string;
  out: string;
  baseUrl: string;
  title: string;
  description: string;
  drafts: boolean;
}

function toConfig(opts: CommonOpts): SiteConfig {
  return { ...DEFAULT_CONFIG, ...opts };
}

function addCommonOptions(cmd: Command): Command {
  return cmd
    .option('-s, --source <dir>', 'source directory of markdown files', DEFAULT_CONFIG.source)
    .option('-t, --templates <dir>', 'directory of Handlebars templates', DEFAULT_CONFIG.templates)
    .option('-o, --out <dir>', 'output directory', DEFAULT_CONFIG.out)
    .option('--base-url <url>', 'base URL for absolute links in the RSS feed', DEFAULT_CONFIG.baseUrl)
    .option('--title <title>', 'site title', DEFAULT_CONFIG.title)
    .option('--description <text>', 'site description', DEFAULT_CONFIG.description)
    .option('--drafts', 'include draft pages', false);
}

export function createProgram(): Command {
  const program = new Command()
    .name('ssg')
    .description('Static site generator: Markdown + YAML frontmatter -> Handlebars -> HTML')
    .version('1.0.0');

  addCommonOptions(
    program
      .command('build')
      .description('build the site once'),
  ).action((opts: CommonOpts) => {
    const config = toConfig(opts);
    const result = buildSite(config);
    console.log(`[ssg] built ${result.pages.length} page(s), ${result.tagPages.length} tag page(s) -> ${config.out}`);
  });

  addCommonOptions(
    program
      .command('serve')
      .description('build, serve, and live-reload on changes')
      .option('-p, --port <port>', 'dev server port', '3000'),
  ).action(async (opts: CommonOpts & { port: string }) => {
    await startDevServer(toConfig(opts), Number(opts.port));
  });

  return program;
}

const isDirectRun =
  process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop() ?? '');
if (isDirectRun) {
  createProgram()
    .parseAsync(process.argv)
    .catch((err: Error) => {
      console.error(`[ssg] error: ${err.message}`);
      process.exit(1);
    });
}
