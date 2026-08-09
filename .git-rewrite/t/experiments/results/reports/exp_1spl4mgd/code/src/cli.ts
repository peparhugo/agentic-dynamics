#!/usr/bin/env node
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { buildSite } from "./build.js";
import { serve } from "./server.js";
import type { BuildOptions } from "./types.js";

export const HELP = `statik — static site generator

Usage:
  statik build [options]   Build the site
  statik serve [options]   Build, watch, and serve with live reload

Options:
  -s, --source <dir>      Markdown source directory      (default: content)
  -t, --templates <dir>   Handlebars template directory  (default: templates)
  -o, --out <dir>         Output directory               (default: dist-site)
  -p, --port <n>          Dev server port                (default: 4000)
      --drafts            Include pages marked draft: true
      --base-url <url>    Site base URL (used in RSS)    (default: http://localhost:4000)
      --title <title>     Site title                     (default: My Site)
      --description <s>   Site description for RSS
  -h, --help              Show this help
  -v, --version           Show version
`;

export interface CliCommand {
  command: "build" | "serve" | "help" | "version";
  options: BuildOptions & { port: number };
}

export function parseCliArgs(argv: string[]): CliCommand {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      source: { type: "string", short: "s", default: "content" },
      templates: { type: "string", short: "t", default: "templates" },
      out: { type: "string", short: "o", default: "dist-site" },
      port: { type: "string", short: "p", default: "4000" },
      drafts: { type: "boolean", default: false },
      "base-url": { type: "string", default: "http://localhost:4000" },
      title: { type: "string", default: "My Site" },
      description: { type: "string", default: "" },
      help: { type: "boolean", short: "h", default: false },
      version: { type: "boolean", short: "v", default: false },
    },
  });

  const port = Number.parseInt(values.port!, 10);
  if (Number.isNaN(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid port: ${values.port}`);
  }

  let command: CliCommand["command"];
  if (values.help) command = "help";
  else if (values.version) command = "version";
  else if (positionals[0] === "build" || positionals[0] === undefined) command = "build";
  else if (positionals[0] === "serve") command = "serve";
  else throw new Error(`Unknown command: ${positionals[0]}`);

  return {
    command,
    options: {
      sourceDir: path.resolve(values.source!),
      templateDir: path.resolve(values.templates!),
      outDir: path.resolve(values.out!),
      includeDrafts: values.drafts!,
      port,
      site: {
        baseUrl: values["base-url"]!,
        title: values.title!,
        description: values.description!,
      },
    },
  };
}

export async function main(argv = process.argv.slice(2)): Promise<void> {
  let cli: CliCommand;
  try {
    cli = parseCliArgs(argv);
  } catch (err) {
    console.error(`Error: ${err instanceof Error ? err.message : err}`);
    console.error(HELP);
    process.exitCode = 1;
    return;
  }

  switch (cli.command) {
    case "help":
      console.log(HELP);
      return;
    case "version": {
      const { readFile } = await import("node:fs/promises");
      const pkgPath = new URL("../package.json", import.meta.url);
      const pkg = JSON.parse(await readFile(pkgPath, "utf8")) as { version: string };
      console.log(pkg.version);
      return;
    }
    case "build": {
      const started = Date.now();
      const result = await buildSite(cli.options);
      console.log(
        `Built ${result.pages.length} page(s), ${result.tagPages.length} tag page(s)` +
          (result.skippedDrafts ? `, skipped ${result.skippedDrafts} draft(s)` : "") +
          ` -> ${cli.options.outDir} in ${Date.now() - started}ms`
      );
      return;
    }
    case "serve":
      await serve(cli.options);
      return;
  }
}

const isDirectRun =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  main().catch((err) => {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
