#!/usr/bin/env node
import { buildSite } from "./build.js";
import { serve } from "./server.js";

export interface CliOptions {
  command: "build" | "serve" | "help";
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  port: number;
  drafts: boolean;
  siteTitle?: string;
  siteUrl?: string;
}

export const USAGE = `ssg - static site generator

Usage:
  ssg build [options]     Build the site once
  ssg serve [options]     Build, serve, watch and live-reload

Options:
  -s, --source <dir>      Source dir of markdown files   (default: content)
  -t, --templates <dir>   Handlebars template dir        (default: templates)
  -o, --output <dir>      Output dir                     (default: dist-site)
  -p, --port <n>          Dev server port                (default: 3000)
      --drafts            Include pages with draft: true
      --site-title <s>    Site title (used in feed/layouts)
      --site-url <s>      Absolute site URL (used in feed)
  -h, --help              Show this help
`;

/** Parse argv (without node/script prefix) into CliOptions. Throws on bad input. */
export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    command: "help",
    sourceDir: "content",
    templateDir: "templates",
    outputDir: "dist-site",
    port: 3000,
    drafts: false,
  };

  const args = [...argv];
  const first = args[0];
  if (first === "build" || first === "serve") {
    opts.command = first;
    args.shift();
  } else if (first === "help" || first === "-h" || first === "--help" || first === undefined) {
    opts.command = "help";
    return opts;
  } else {
    throw new Error(`Unknown command: ${first}`);
  }

  const takeValue = (flag: string): string => {
    const v = args.shift();
    if (v === undefined) throw new Error(`Missing value for ${flag}`);
    return v;
  };

  while (args.length > 0) {
    const arg = args.shift()!;
    switch (arg) {
      case "-s":
      case "--source":
        opts.sourceDir = takeValue(arg);
        break;
      case "-t":
      case "--templates":
        opts.templateDir = takeValue(arg);
        break;
      case "-o":
      case "--output":
        opts.outputDir = takeValue(arg);
        break;
      case "-p":
      case "--port": {
        const n = Number(takeValue(arg));
        if (!Number.isInteger(n) || n < 1 || n > 65535) throw new Error(`Invalid port: ${n}`);
        opts.port = n;
        break;
      }
      case "--drafts":
        opts.drafts = true;
        break;
      case "--site-title":
        opts.siteTitle = takeValue(arg);
        break;
      case "--site-url":
        opts.siteUrl = takeValue(arg);
        break;
      case "-h":
      case "--help":
        opts.command = "help";
        return opts;
      default:
        throw new Error(`Unknown option: ${arg}`);
    }
  }
  return opts;
}

export async function main(argv: string[]): Promise<number> {
  let opts: CliOptions;
  try {
    opts = parseArgs(argv);
  } catch (err) {
    console.error(String(err instanceof Error ? err.message : err));
    console.error(USAGE);
    return 2;
  }

  if (opts.command === "help") {
    console.log(USAGE);
    return 0;
  }

  const site = {
    ...(opts.siteTitle !== undefined ? { title: opts.siteTitle } : {}),
    ...(opts.siteUrl !== undefined ? { url: opts.siteUrl } : {}),
  };

  try {
    if (opts.command === "build") {
      const result = await buildSite({
        sourceDir: opts.sourceDir,
        templateDir: opts.templateDir,
        outputDir: opts.outputDir,
        drafts: opts.drafts,
        site,
      });
      console.log(`[ssg] wrote ${result.written.length} files to ${opts.outputDir}`);
      return 0;
    }
    await serve({
      sourceDir: opts.sourceDir,
      templateDir: opts.templateDir,
      outputDir: opts.outputDir,
      drafts: opts.drafts,
      site,
      port: opts.port,
    });
    return 0;
  } catch (err) {
    console.error(`[ssg] error: ${err instanceof Error ? err.message : String(err)}`);
    return 1;
  }
}

// Only run when executed directly, not when imported by tests.
if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => {
    if (code !== 0) process.exitCode = code;
  });
}
