import { main, HelpError } from './cli';

main(process.argv.slice(2)).catch((err: unknown) => {
  if (err instanceof HelpError) {
    process.stderr.write(`${err.message}\n`);
    process.exit(0);
  }
  const message = err instanceof Error ? err.message : String(err);
  process.stderr.write(`Error: ${message}\n`);
  process.exit(1);
});
