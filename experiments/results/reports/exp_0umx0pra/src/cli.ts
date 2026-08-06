import { Command } from 'commander';
import { SiteConfig } from './types';

export function parseArgs(argv: string[]): SiteConfig {
  const program = new Command();

  program
    .name('ssg')
    .description('Static site generator with Markdown, Handlebars, and live reload')
    .requiredOption('-s, --source <dir>', 'Source directory of Markdown files')
    .requiredOption('-t, --templates <dir>', 'Template directory of Handlebars files')
    .requiredOption('-o, --output <dir>', 'Output directory for generated HTML')
    .option('-d, --dev', 'Run in dev mode with live reload server')
    .option('-p, --port <port>', 'Dev server port', '3000')
    .option('--drafts', 'Include draft pages')
    .option('--title <title>', 'Site title', 'My Site')
    .option('--url <url>', 'Site URL for RSS feed', 'http://localhost:3000')
    .exitOverride();

  try {
    program.parse(argv);
  } catch (err: any) {
    if (err.code === 'commander.missingRequiredOption') {
      throw new Error(`Missing required option: ${err.message}`);
    }
    throw err;
  }

  const opts = program.opts<{
    source: string;
    templates: string;
    output: string;
    dev?: boolean;
    port: string;
    drafts?: boolean;
    title: string;
    url: string;
  }>();

  return {
    sourceDir: opts.source,
    templateDir: opts.templates,
    outputDir: opts.output,
    devMode: opts.dev || false,
    port: parseInt(opts.port, 10),
    includeDrafts: opts.drafts || false,
    siteTitle: opts.title,
    siteUrl: opts.url,
  };
}
