/**
 * Journal Island mount logic.
 *
 * Dynamically imported by `main.ts` when a `[data-island="journal"]` element is
 * found. The journal fetches all its data from the JSON API on mount, so no
 * server-provided props are needed; the signature stays uniform with the island
 * contract so the registry treats every island identically.
 */
import { createRoot } from 'react-dom/client'
import { JournalIsland } from './JournalIsland'

/**
 * Mount the JournalIsland into the given element.
 *
 * @param element - DOM element (the data-island div) to render into.
 * @param _props  - Unused; the journal loads its own data from the API.
 */
export function mount(element: HTMLElement, _props: unknown): void {
  // Clear the server-rendered fallback (e.g. the <noscript> notice).
  element.innerHTML = ''

  const root = createRoot(element)
  root.render(<JournalIsland />)
}
