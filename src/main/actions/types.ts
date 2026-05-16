// Common types for action handlers.

import type { Page } from 'playwright';
import type { AppConfig, StepAction, TaskData } from '../types';

export interface RenderedFields {
  selector: string;
  value: string;
  url: string;
  expected: string;
}

export interface ActionContext {
  page: Page;
  step: StepAction;
  task: TaskData;
  cfg: AppConfig;
  vars: Map<string, string>;
  attempt: number;
  shouldStop: () => boolean;
  log: (msg: string) => void;
  rendered: RenderedFields;
  timeoutMs: number;
  timeoutSec: number;
}

export type ActionHandler = (ctx: ActionContext) => Promise<void>;

export class StepError extends Error {
  override readonly name = 'StepError';
}
