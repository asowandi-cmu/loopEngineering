/**
 * Bullet entity — shared by the player and the aliens.
 *
 * A bullet is a tiny rectangle that travels vertically at a constant speed.
 * The sign of `speed` encodes direction (negative = up for player shots,
 * positive = down for alien shots), so a single class serves both without a
 * subclass or a `direction` flag — the velocity *is* the direction.
 */
import type { Dimensions, Entity, Position } from './types'
import { BULLET_HEIGHT, BULLET_WIDTH, CANVAS_HEIGHT } from './constants'

export class Bullet implements Entity {
  position: Position
  dimensions: Dimensions
  /** Vertical velocity in px/s. Negative = upward, positive = downward. */
  speed: number
  alive = true

  constructor(x: number, y: number, speed: number) {
    this.position = { x, y }
    this.dimensions = { width: BULLET_WIDTH, height: BULLET_HEIGHT }
    this.speed = speed
  }

  /**
   * Advance the bullet by `dt` seconds and retire it once fully off-screen.
   *
   * Marking off-screen bullets as not-alive (rather than leaving them to drift
   * forever) is what lets the owning array prune them, preventing an unbounded
   * memory/processing leak from rapid firing.
   */
  update(dt: number): void {
    this.position.y += this.speed * dt
    if (
      this.position.y + this.dimensions.height < 0 ||
      this.position.y > CANVAS_HEIGHT
    ) {
      this.alive = false
    }
  }
}
