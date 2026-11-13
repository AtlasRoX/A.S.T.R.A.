import type { KeyboardEvent } from 'react';

/**
 * Arrow-key navigation for a `role="radiogroup"` made of `role="radio"` buttons.
 *
 * Left/Up and Right/Down move to the previous and next radio (wrapping), Home/End jump to the ends, and the
 * newly focused radio is activated, which is how native radios behave. Attach it as `onKeyDown` on the group.
 */
export function radioGroupKeys(e: KeyboardEvent<HTMLElement>) {
  const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'];
  if (!keys.includes(e.key)) return;
  const radios = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]:not([disabled])'));
  if (!radios.length) return;
  const current = radios.indexOf(document.activeElement as HTMLElement);
  let next = current;
  if (e.key === 'Home') next = 0;
  else if (e.key === 'End') next = radios.length - 1;
  else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (current + 1) % radios.length;
  else next = (current - 1 + radios.length) % radios.length;
  e.preventDefault();
  radios[next].focus();
  radios[next].click();
}

/**
 * Arrow-key navigation for a `role="tablist"` of `role="tab"` elements (buttons or links).
 *
 * Left/Up and Right/Down move focus to the previous and next tab (wrapping); Home/End jump to the ends.
 * Activation stays manual (Enter or Space), so moving along a list of links does not navigate on every key.
 */
export function tabListKeys(e: KeyboardEvent<HTMLElement>) {
  const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'];
  if (!keys.includes(e.key)) return;
  const tabs = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]:not([disabled])'));
  if (!tabs.length) return;
  const current = tabs.indexOf(document.activeElement as HTMLElement);
  let next = current;
  if (e.key === 'Home') next = 0;
  else if (e.key === 'End') next = tabs.length - 1;
  else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (current + 1) % tabs.length;
  else next = (current - 1 + tabs.length) % tabs.length;
  e.preventDefault();
  tabs[next].focus();
}
