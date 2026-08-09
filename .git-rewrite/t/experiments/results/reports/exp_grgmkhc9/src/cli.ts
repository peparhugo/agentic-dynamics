import { SiteConfig } from "./types";

export function parseArgs(args: string[]): SiteConfig {
  const config: SiteConfig = {
    sourceDir: "./content",
    templateDir: "./templates",
    outputDir: "./dist",
    siteTitle: "My Static Site",
    siteUrl: "http://localhost:3000",
    port: 3000,
    serve: false,
    watch: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    switch (arg) {
      case "-s":
      case "--source":
        if (next && !next.startsWith("-")) {
          config.sourceDir = next;
          i++;
        }
        break;
      case "-t":
      case "--templates":
        if (next && !next.startsWith("-")) {
          config.templateDir = next;
          i++;
        }
        break;
      case "-o":
      case "--output":
        if (next && !next.startsWith("-")) {
          config.outputDir = next;
          i++;
        }
        break;
      case "-p":
      case "--port":
        if (next && !next.startsWith("-")) {
          config.port = parseInt(next, 10);
          i++;
        }
        break;
      case "--title":
        if (next && !next.startsWith("-")) {
          config.siteTitle = next;
          i++;
        }
        break;
      case "--url":
        if (next && !next.startsWith("-")) {
          config.siteUrl = next;
          i++;
        }
        break;
      case "-S":
      case "--serve":
        config.serve = true;
        break;
      case "-w":
      case "--watch":
        config.watch = true;
        break;
    }
  }

  return config;
}

export function printHelp(): string {
  return `statico - Static Site Generator

Usage: statico [options]

Options:
  -s, --source <dir>     Source directory of Markdown files (default: ./content)
  -t, --templates <dir>  Template directory of Handlebars files (default: ./templates)
  -o, --output <dir>     Output directory for generated HTML (default: ./dist)
  -p, --port <number>    Dev server port (default: 3000)
  --title <string>       Site title (default: "My Static Site")
  --url <string>         Site base URL for RSS (default: "http://localhost:3000")
  -S, --serve            Start dev server with live reload
  -w, --watch            Watch for changes and rebuild
  -h, --help             Show this help message
`;
}
