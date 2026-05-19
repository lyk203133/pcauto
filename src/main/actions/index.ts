// Action registry — maps action name -> handler. Unknown actions are routed
// to a no-op handler that just logs a warning (matches Rust).

import type { ActionHandler } from './types';
import { navigate } from './navigate';
import { captchaPrefetch } from './captchaPrefetch';
import { input } from './input';
import { typeAction } from './type';
import { click } from './click';
import { select } from './select';
import { dropdown } from './dropdown';
import { waitText } from './waitText';
import { waitSelector } from './waitSelector';
import { waitGa } from './waitGa';
import { captchaImage } from './captchaImage';
import { wait } from './wait';
import { screenshot } from './screenshot';
import { js } from './js';
import { scroll } from './scroll';
import { keyboardType } from './keyboardType';

export const actionRegistry: Record<string, ActionHandler> = {
  navigate,
  captcha_prefetch: captchaPrefetch,
  input,
  type: typeAction,
  click,
  select,
  dropdown,
  wait_text: waitText,
  wait_selector: waitSelector,
  wait_ga: waitGa,
  captcha_image: captchaImage,
  request_captcha: captchaImage,
  captcha: captchaImage,
  wait,
  screenshot,
  js,
  scroll,
  keyboard_type: keyboardType,
};

export function lookupAction(name: string): ActionHandler | undefined {
  return Object.prototype.hasOwnProperty.call(actionRegistry, name)
    ? actionRegistry[name]
    : undefined;
}
