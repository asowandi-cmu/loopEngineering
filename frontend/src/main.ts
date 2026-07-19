/**
 * Island Registry and Auto-Mount System
 *
 * This is the core of the React Islands architecture. It:
 * 1. Scans the DOM for [data-island] elements
 * 2. Dynamically imports the corresponding island module
 * 3. Mounts the React component with props from data-props
 *
 * Why Islands?
 * - Progressive enhancement: HTML works without JS
 * - Partial hydration: Only load JS for interactive parts
 * - Colocated concerns: Each island is self-contained
 */
import './styles/globals.css'

/**
 * Island module interface - each island exports a mount function.
 */
interface IslandModule {
  mount: (element: HTMLElement, props: unknown) => void
}

/**
 * Registry of island name to dynamic import function.
 * Add new islands here as they are created.
 */
const islandRegistry: Record<string, () => Promise<IslandModule>> = {
  journal: () => import('./islands/journal'),
}

/**
 * Parse props from data-props attribute.
 * Returns empty object if attribute is missing or invalid.
 */
function parseProps(element: HTMLElement): unknown {
  const propsAttr = element.getAttribute('data-props')
  if (!propsAttr) return {}

  try {
    return JSON.parse(propsAttr)
  } catch (e) {
    console.error('Failed to parse island props:', e)
    return {}
  }
}

/**
 * Mount all islands found in the DOM.
 * Called on DOMContentLoaded.
 */
async function mountIslands(): Promise<void> {
  const islands = document.querySelectorAll<HTMLElement>('[data-island]')

  for (const element of islands) {
    const islandName = element.getAttribute('data-island')
    if (!islandName) continue

    const importFn = islandRegistry[islandName]
    if (!importFn) {
      console.warn(`Unknown island: ${islandName}`)
      continue
    }

    try {
      const module = await importFn()
      const props = parseProps(element)
      module.mount(element, props)
    } catch (e) {
      console.error(`Failed to mount island "${islandName}":`, e)
    }
  }
}

// Mount islands when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountIslands)
} else {
  mountIslands()
}
