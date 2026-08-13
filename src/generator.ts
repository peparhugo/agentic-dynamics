
export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const { createEngine } = await import('./engine');
  return (await createEngine()).build(options);
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<{ pages: Page[]; stats: BuildStats }> {
  const { createEngine } = await import('./engine');
  const engine = await createEngine();
  const pages = await engine.build(options);
  return { pages, stats: engine.lastBuildStats };
}
