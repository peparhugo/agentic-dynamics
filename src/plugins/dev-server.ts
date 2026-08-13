import { BuildContext, Plugin } from '../types';

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  constructor(private readonly reload: () => void = () => undefined) {}

  afterBuild(_context: BuildContext): void {
    this.reload();
  }
}
