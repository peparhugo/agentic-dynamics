import { SsgEngine } from './engine';

export interface BuildOptions {
  incremental?: boolean;
  clean?: boolean;
}

export function build(contentDir: string, outputDir: string, templatesDir?: string, options?: BuildOptions): void {
  const engine = new SsgEngine();
  engine.build(contentDir, outputDir, templatesDir, options);
}
