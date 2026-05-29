/**
 * Core game type definitions for the Space Invaders engine.
 *
 * These types are deliberately framework-agnostic (no React, no DOM beyond
 * the canvas context passed to the Renderer). Keeping them isolated lets the
 * engine be unit-tested and reused independently of the Islands wrapper.
 */

/** A point in canvas space. Origin is top-left; +y points down. */
export interface Position {
  x: number
  y: number
}

/** Width/height of an axis-aligned rectangle, in pixels. */
export interface Dimensions {
  width: number
  height: number
}

/**
 * High-level game lifecycle states.
 *
 * - `start`    — title screen, waiting for the player to begin.
 * - `playing`  — active gameplay; the only state the game loop simulates.
 * - `gameover` — player was hit or aliens reached the bottom.
 * - `won`      — every alien has been destroyed.
 *
 * The loop only advances simulation in `playing`; other states just render a
 * static screen, which is why the loop can keep running cheaply after the
 * round ends (and lets the player restart with Space).
 */
export type GameState = 'start' | 'playing' | 'gameover' | 'won'

/**
 * Anything with a position, size, and alive flag.
 *
 * `alive` is the single source of truth for whether an entity participates in
 * updates, rendering, and collision checks. Dead entities are pruned by their
 * owning collection (e.g. the bullets array) rather than mutated in place.
 */
export interface Entity {
  position: Position
  dimensions: Dimensions
  alive: boolean
}
