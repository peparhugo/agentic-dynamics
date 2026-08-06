#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { build, type BuildOptions } from "./build.js";
import { serve } from "./server.js";

export interface CliOptions extends BuildOptions {
  command: "build" | "serve";
  port: number;
  help: boolean;
}

export const USAGE = `sitegen - static site generator

Usage:
  sitegen build [options]   Build the site once
  sitegen serve [options]   Build, serve, watch, and live-reload

Options:
  -s, --source <dir>       Markdown source directory      (default: content)
  -t, --templates <dir>    Handlebars template directory  (default: templates)
  -o, --output <dir>       Output directory               (default: dist)
  -p, --port <n>           Dev server port                (default: 3000)
      --drafts             Include pages marked draft: true
      --site-title <s>     Site title (used in RSS)       (default: Site)
      --site-desc <s>      Site description (used in RSS)
      --site-url <url>     Canonical site URL (used in RSS)
  -h, --help               Show this help
`;

/** Parse argv (without node/script prefix) into CLI options. Throws on bad input. */
export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    command: "build",
    sourceDir: "content",
    templateDir: "templates",
    outputDir: "dist",
    port: 3000,
    drafts: false,
    siteTitle: "Site",
    siteDescription: "",
    siteUrl: "http://localhost:3000",
    help: false,
  };

  const args = [...argv];
  if (args[0] === "build" || args[0] === "serve") {
    opts.command = args.shift() as "build" | "serve";
  }

  const next = (flag: string): string => {
    const value = args.shift();
    if (value === undefined || value.startsWith("-")) {
      throw new Error(`Missing value for ${flag}`);
    }
    return value;
  };

  while (args.length > 0) {
    const arg = args.shift()!;
    switch (arg) {
      case "-s":
      case "--source":
        opts.sourceDir = next(arg);
        break;
      case "-t":
      case "--templates":
        opts.templateDir = next(arg);
        break;
      case "-o":
      case "--output":
        opts.outputDir = next(arg);
        break;
      case "-p":
      case "--port": {
        const port = Number(next(arg));
        if (!Number.isInteger(port) || port < 0 || port > 65535) {
          throw new Error(`Invalid port: ${port}`);
        }
        opts.port = port;
        break;
      }
      case "--drafts":
        opts.drafts = true;
        break;
      case "--site-title":
        opts.siteTitle = next(arg);
        break;
      case "--site-desc":
        opts.siteDescription = next(arg);
        break;
      case "--site-url":
        opts.siteUrl = next(arg);
        break;
      case "-h":
      case "--help":
        opts.help = true;
        break;
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

  if (opts.help) {
    console.log(USAGE);
    return 0;
  }

  try {
    if (opts.command === "serve") {
      await serve(opts);
      return 0; // stays alive via open server handles
    }
    const result = await build(opts);
    console.log(
      `[sitegen] built ${result.pages.length} page(s), ` +
        `${result.tagPages.length} tag page(s), feed.xml -> ${opts.outputDir}`
    );
    return 0;
  } catch (err) {
    console.error("[sitegen] error:", err instanceof Error ? err.message : err);
    return 1;
  }
}

const isDirectRun =
  process.argv[1] && fileURLToPath(import.meta.url) === (await import("node:path")).resolve(process.argv[1]);
if (isDirectRun) {
  process.exitCode = await main(process.argv.slice(2));
}
