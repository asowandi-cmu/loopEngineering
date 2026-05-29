/**
 * Shared TypeScript types for the application.
 *
 * These types are used across islands and components. Game-specific types
 * live in `frontend/src/game/types.ts` so the framework-agnostic engine has
 * no dependency on app-level concerns.
 */

/**
 * Props passed to islands via the `data-props` attribute.
 *
 * Each island receives its initial data from the server. The Space Invaders
 * game needs no server data (it is fully client-side), but the type is kept
 * generic so future islands can pass typed initial state.
 */
export type IslandProps<T = unknown> = {
  initialData?: T
}
