/**
 * Shared TypeScript types for the application.
 *
 * These types are used across islands and components. Feature-specific types
 * live alongside their island (e.g. `frontend/src/journal/types.ts`) so each
 * island stays self-contained.
 */

/**
 * Props passed to islands via the `data-props` attribute.
 *
 * Each island receives its initial data from the server. The journal island
 * loads its own data from the JSON API on mount, but the type is kept generic
 * so future islands can pass typed initial state.
 */
export type IslandProps<T = unknown> = {
  initialData?: T
}
