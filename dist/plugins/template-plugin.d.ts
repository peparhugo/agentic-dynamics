import { Plugin, BuildContext } from '../plugin';
import { Page } from '../types';
export declare class TemplatePlugin implements Plugin {
    name: string;
    private engine;
    onStart(context: BuildContext): void;
    onFile(page: Page, context: BuildContext): void;
    afterBuild(context: BuildContext): void;
}
//# sourceMappingURL=template-plugin.d.ts.map