import type { Plugin } from '../plugin';
import type { SsgEngine } from '../engine';
import type { ServeOptions, DevServer } from '../serve';
export declare class DevServerPlugin implements Plugin {
    private readonly engine;
    readonly name = "devServer";
    constructor(engine: SsgEngine);
    start(options: ServeOptions): Promise<DevServer>;
}
