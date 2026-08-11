import { Page } from './types';
export interface BuildContext {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
}
export interface Plugin {
    name: string;
    setContext?(context: BuildContext): void;
    onStart?(): void;
    beforeBuild?(): void;
    onFile?(page: Page): void;
    afterBuild?(pages: Page[]): void;
    onEnd?(): void;
}
//# sourceMappingURL=plugin.d.ts.map