#!/usr/bin/env node
import path from "node:path";
import { buildSite } from "./build.js";
import { startDevServer } from "./server.js";
import type { SiteConfig } from "./types.js";

const HELP = `ssg - static site generator

Usage:
  ssg build [options]   Build the site once
  ssg serve [options]   Build, serve, and live-reload on changes

Options:
  -s, --source <dir>      Source directory of Markdown files   (default: content)
  -t, --templates <dir>   Handlebars template directory        (default: templates)
  -o, --output <dir>      Output directory                     (default: dist-site)
  -p, --port <port>       Dev server port (serve only)         (default: 3000)
      --drafts            Include pages marked draft: true
      --site-title <s>    Site title for RSS                   (default: "My Site")
      --site-url <s>      Absolute site URL for RSS            (default: "http://localhost:3000")
      --site-desc <s>     Site description for RSS
  -h, --help              Show this help
`;

export interface CliOptions {
  command: "build" | "serve" | "help";
  config: SiteConfig;
  port: number;
}

export class CliError extends Error {}

/** Parse argv (without node/script prefix) into structured options. */
export function parseArgs(argv: string[]): CliOptions {
  let command: CliOptions["command"] | null = null;
  const opts = {
    source: "content",
    templates: "templates",
    output: "dist-site",
    port: 3000,
    drafts: false,
    siteTitle: "My Site",
    siteUrl: "http://localhost:3000",
    siteDesc: "",
  };

  const takeValue = (flag: string, i: number): string => {
    const v = argv[i + 1];
    if (v === undefined || v.startsWith("-")) throw new CliError(`Missing value for ${flag}`);
    return v;
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case "build":
      case "serve":
        if (command) throw new CliError(`Unexpected extra command "${arg}"`);
        command = arg;
        break;
      case "-s":
      case "--source":
        opts.source = takeValue(arg, i++);
        break;
      case "-t":
      case "--templates":
        opts.templates = takeValue(arg, i++);
        break;
      case "-o":
      case "--output":
        opts.output = takeValue(arg, i++);
        break;
      case "-p":
      case "--port": {
        const raw = takeValue(arg, i++);
        const port = Number(raw);
        if (!Number.isInteger(port) || port < 0 || port > 65535) {
          throw new CliError(`Invalid port: ${raw}`);
        }
        opts.port = port;
        break;
      }
      case "--drafts":
        opts.drafts = true;
        break;
      case "--site-title":
        opts.siteTitle = takeValue(arg, i++);
        break;
      case "--site-url":
        opts.siteUrl = takeValue(arg, i++);
        break;
      case "--site-desc":
        opts.siteDesc = takeValue(arg, i++);
        break;
      case "-h":
      case "--help":
        command = "help";
        break;
      default:
        throw new CliError(`Unknown argument: ${arg}`);
    }
    if (command === "help") break;
  }

  if (!command) throw new CliError('Missing command: expected "build" or "serve"');

  return {
    command,
    port: opts.port,
    config: {
      sourceDir: path.resolve(opts.source),
      templateDir: path.resolve(opts.templates),
      outputDir: path.resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
      siteDescription: opts.siteDesc,
      includeDrafts: opts.drafts,
    },
  };
}

export async function main(argv: string[]): Promise<number> {
  let options: CliOptions;
  try {
    options = parseArgs(argv);
  } catch (err) {
    if (err instanceof CliError) {
      console.error(`Error: ${err.message}\n`);
      console.error(HELP);
      return 2;
    }
    throw err;
  }

  if (options.command === "help") {
    console.log(HELP);
    return 0;
  }

  if (options.command === "build") {
    const start = performance.now();
    const result = await buildSite(options.config);
    const ms = (performance.now() - start).toFixed(0);
    console.log(
      `Built ${result.pages.length} page(s), ${result.tagPages.length} tag page(s), feed.xml in ${ms}ms` +
        (result.skippedDrafts ? ` (skipped ${result.skippedDrafts} draft(s))` : "")
    );
    return 0;
  }

  await startDevServer(options.config, options.port);
  return 0;
}

// Only run when executed directly, not when imported by tests.
const isDirect = process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]));
if (isDirect) {
  main(process.argv.slice(2))
    .then((code) => {
      if (code !== 0) process.exitCode = code;
    })
    .catch((err) => {
      console.error(err);
      process.exitCode = 1;
    });
}
