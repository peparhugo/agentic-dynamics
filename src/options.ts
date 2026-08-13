export interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export function parseBuildOptions(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];
    if (value === '--content' || value === '--output' || value === '--templates') {
      const path = args[++index];
      if (!path) throw new Error(`Missing value for ${value}`);
      if (value === '--content') options.contentDir = path;
      else if (value === '--output') options.outputDir = path;
      else options.templatesDir = path;
    } else {
      throw new Error(`Unknown option: ${value}`);
    }
  }
  return options;
}
