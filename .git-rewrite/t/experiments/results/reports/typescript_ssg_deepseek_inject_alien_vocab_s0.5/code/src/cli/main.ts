#!/usr/bin/env node

import { buildSite } from "../lib/builder";
import { serve } from "../server/dev";
import * as path from "path";

interface Args {
  command: "build" | "serve";
  source: string;
  templates: string;
  output: string;
  port: number;
}

export function parseArgs(raw: string[]): Args {
  const args: Args = {
    command: "build",
    source: "content",
    templates: "templates",
    output: "dist",
    port: 3000,
  };

  for (let i = 0; i < raw.length; i++) {
    switch (raw[i]) {
      case "serve":
        args.command = "serve";
        break;
      case "build":
        args.command = "build";
        break;
      case "-s":
      case "--source":
        args.source = raw[++i] || args.source;
        break;
      case "-t":
      case "--templates":
        args.templates = raw[++i] || args.templates;
        break;
      case "-o":
      case "--output":
        args.output = raw[++i] || args.output;
        break;
      case "-p":
      case "--port":
        args.port = parseInt(raw[++i] || "3000", 10);
        break;
    }
  }

  return args;
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));

  const sourceDir = path.resolve(args.source);
  const templateDir = path.resolve(args.templates);
  const outputDir = path.resolve(args.output);

  if (args.command === "serve") {
    serve(sourceDir, templateDir, outputDir, args.port);
  } else {
    console.log(`[statick] building from ${sourceDir}...`);
    const ctx = buildSite(sourceDir, templateDir, outputDir);
    console.log(
      `[statick] done — ${ctx.posts.length} posts, ${ctx.tags.length} tags → ${outputDir}`
    );
  }
}

main();
