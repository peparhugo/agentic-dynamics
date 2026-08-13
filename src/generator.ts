
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
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const { createEngine } = await import('./engine');
  return (await createEngine()).build(options);
}
