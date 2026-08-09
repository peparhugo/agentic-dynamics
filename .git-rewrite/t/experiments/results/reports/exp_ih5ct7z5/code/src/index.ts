#!/usr/bin/env node

import { resolve } from "path";
import { generateSite } from "./generator";
import { startDevServer } from "./server";
import { SiteConfig } from "./types";

function showHelp(): void {
  console.log(`
Static Site Generator (ssg)

Usage: ssg [options]

Options:
  --source, -s       Source directory of Markdown files        [required]
  --templates, -t    Template directory of Handlebars files     [required]
  --output, -o       Output directory for generated site        [required]
  --serve            Start dev server with live reload
  --port, -p         Port for dev server          [default: 3000]
  --title            Site title                    [default: "My Site"]
  --description      Site description              [default: ""]
  --base-url         Base URL for RSS feed        [default: "http://localhost:3000"]
  --help, -h         Show this help

Examples:
  ssg --source content --templates theme --output public
  ssg -s content -t theme -o public --serve --port 8080
  ssg -s src -t tpl -o dist --title "My Blog" --base-url "https://example.com"
  `);
}

function parseArgs(args: string[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--help" || arg === "-h") {
      result.help = "true";
      continue;
    }
    if (arg === "--serve") {
      result.serve = "true";
      continue;
    }
    const next = args[i + 1];
    if (next === undefined || next.startsWith("-")) continue;

    switch (arg) {
      case "--source":
      case "-s":
        result.source = next;
        i++;
        break;
      case "--templates":
      case "-t":
        result.templates = next;
        i++;
        break;
      case "--output":
      case "-o":
        result.output = next;
        i++;
        break;
      case "--port":
      case "-p":
        result.port = next;
        i++;
        break;
      case "--title":
        result.title = next;
        i++;
        break;
      case "--description":
        result.description = next;
        i++;
        break;
      case "--base-url":
        result["base-url"] = next;
        i++;
        break;
    }
  }
  return result;
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    showHelp();
    return;
  }

  if (!args.source || !args.templates || !args.output) {
    console.error("Error: --source, --templates, and --output are required.");
    console.error("Use --help for usage information.");
    process.exit(1);
  }

  const sourceDir = resolve(args.source);
  const templateDir = resolve(args.templates);
  const outputDir = resolve(args.output);
  const port = parseInt(args.port || "3000", 10);

  const config: SiteConfig = {
    title: args.title || "My Site",
    description: args.description || "",
    baseUrl: args["base-url"] || `http://localhost:${port}`,
  };

  if (args.serve === "true") {
    startDevServer(sourceDir, templateDir, outputDir, port, config);
  } else {
    console.log(`Building site from ${sourceDir} to ${outputDir}...`);
    generateSite(sourceDir, templateDir, outputDir, config);
    console.log("Site built successfully.");
  }
}

main();
