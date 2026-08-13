export interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

export function parseOptions(args: string[], includePort = false): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];
    if (value === '--content' || value === '--output' || value === '--templates' || (includePort && value === '--port')) {
      const path = args[++index];
      if (!path) throw new Error(`Missing value for ${value}`);
      if (value === '--content') options.contentDir = path;
      else if (value === '--output') options.outputDir = path;
      else if (value === '--templates') options.templatesDir = path;
      else {
        const port = Number(path);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${path}`);
        options.port = port;
      }
    } else {
      throw new Error(`Unknown option: ${value}`);
    }
  }
  return options;
}

export function parseBuildOptions(args: string[]): CliOptions {
  return parseOptions(args);
}

export function parseServeOptions(args: string[]): CliOptions {
  return parseOptions(args, true);
}
