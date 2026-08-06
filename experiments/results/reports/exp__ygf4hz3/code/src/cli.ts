import { Command } from 'commander';
import { CLIOptions } from './types';

export function parseArgs(argv: string[]): CLIOptions & { command: string } {
  const program = new Command();

  program.name('static-gen').description('Static site generator from Markdown files').version('1.0.0');

  program
    .command('build')
    .description('Build the static site')
    .requiredOption('-s, --source <path>', 'Source directory of Markdown files')
    .requiredOption('-t, --templates <path>', 'Templates directory')
    .requiredOption('-o, --output <path>', 'Output directory')
    .option('-d, --drafts', 'Include draft pages', false)
    .action(() => {});

  program
    .command('serve')
    .description('Start dev server with live reload')
    .requiredOption('-s, --source <path>', 'Source directory of Markdown files')
    .requiredOption('-t, --templates <path>', 'Templates directory')
    .requiredOption('-o, --output <path>', 'Output directory')
    .option('-p, --port <number>', 'Port to listen on', '3000')
    .option('-d, --drafts', 'Include draft pages', false)
    .action(() => {});

  program.parse(argv);

  const cmd = program.args[0] || 'build';
  const subCmd = program.commands.find(c => c.name() === cmd);
  const opts = subCmd ? subCmd.opts() : program.opts();

  return {
    command: cmd,
    source: (opts as Record<string, unknown>).source as string,
    templates: (opts as Record<string, unknown>).templates as string,
    output: (opts as Record<string, unknown>).output as string,
    port: parseInt(((opts as Record<string, unknown>).port as string) || '3000', 10),
    drafts: Boolean((opts as Record<string, unknown>).drafts),
  };
}
