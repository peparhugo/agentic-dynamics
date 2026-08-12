import { Page } from './page';
import { DEFAULT_TEMPLATES_DIR } from './constants';
import { listMarkdownFiles } from './files';
import { BuildResult, IncrementalBuildOptions, createEngine } from './ssg';

export { DEFAULT_TEMPLATES_DIR, listMarkdownFiles };

export function buildSite(contentDir: string, outputDir: string, templatesDir: string = DEFAULT_TEMPLATES_DIR): Page[] {
  const engine = createEngine({ contentDir, outputDir, templatesDir });
  engine.start();
  return engine.build();
}

export function buildSiteIncremental(
  contentDir: string,
  outputDir: string,
  templatesDir: string = DEFAULT_TEMPLATES_DIR,
  options: IncrementalBuildOptions = {}
): BuildResult {
  const engine = createEngine({ contentDir, outputDir, templatesDir });
  engine.start();
  return engine.buildIncremental(options);
}
