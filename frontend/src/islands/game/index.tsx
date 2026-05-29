/**
 * Game Island mount logic.
 *
 * Dynamically imported by `main.ts` when a `[data-island="game"]` element is
 * found in the DOM. The game needs no server-provided props (it is entirely
 * client-side), so `props` is ignored; the signature is kept uniform with the
 * island contract so the registry can treat all islands identically.
 */
import { createRoot } from 'react-dom/client'
import { GameIsland } from './GameIsland'

/**
 * Mount the GameIsland into the given element.
 *
 * @param element - DOM element (the data-island div) to render into.
 * @param _props  - Unused; the game carries no server-provided state.
 */
export function mount(element: HTMLElement, _props: unknown): void {
  // Clear the server-rendered fallback (e.g. the <noscript> notice).
  element.innerHTML = ''

  const root = createRoot(element)
  root.render(<GameIsland />)
}
