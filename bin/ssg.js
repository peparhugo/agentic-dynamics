#!/usr/bin/env node
import('../lib/cli.js').then(({ run }) => run(process.argv.slice(2))).catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
