/**
 * Player ship entity.
 *
 * Owns its position/size and movement, and knows how to spawn a bullet from
 * its muzzle. Movement is clamped to the canvas so the ship can never leave
 * the playfield (spec edge case). A shot cooldown rate-limits firing so that
 * holding Space doesn't emit one bullet per frame.
 */
import { Bullet } from './Bullet'
import type { Dimensions, Entity, Position } from './types'
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  PLAYER_BOTTOM_MARGIN,
  PLAYER_BULLET_SPEED,
  PLAYER_HEIGHT,
  PLAYER_SHOOT_COOLDOWN,
  PLAYER_SPEED,
  PLAYER_WIDTH,
} from './constants'

export class Player implements Entity {
  position: Position
  dimensions: Dimensions
  speed = PLAYER_SPEED
  alive = true
  /** Seconds remaining until the player may fire again. */
  private cooldown = 0

  constructor() {
    this.dimensions = { width: PLAYER_WIDTH, height: PLAYER_HEIGHT }
    this.position = {
      x: (CANVAS_WIDTH - PLAYER_WIDTH) / 2,
      y: CANVAS_HEIGHT - PLAYER_HEIGHT - PLAYER_BOTTOM_MARGIN,
    }
  }

  /** Move left by `dt` seconds of travel, clamped to the left edge. */
  moveLeft(dt: number): void {
    this.position.x = Math.max(0, this.position.x - this.speed * dt)
  }

  /** Move right by `dt` seconds of travel, clamped to the right edge. */
  moveRight(dt: number): void {
    this.position.x = Math.min(
      CANVAS_WIDTH - this.dimensions.width,
      this.position.x + this.speed * dt,
    )
  }

  /** Tick the firing cooldown down toward zero. */
  update(dt: number): void {
    if (this.cooldown > 0) this.cooldown = Math.max(0, this.cooldown - dt)
  }

  /** True when the ship is off cooldown and allowed to fire. */
  canShoot(): boolean {
    return this.cooldown <= 0
  }

  /**
   * Fire a bullet from the ship's centre, or return `null` if still on
   * cooldown. Returning `null` (rather than throwing) lets the caller simply
   * ignore a too-soon trigger.
   */
  shoot(): Bullet | null {
    if (!this.canShoot()) return null
    this.cooldown = PLAYER_SHOOT_COOLDOWN
    const muzzleX = this.position.x + this.dimensions.width / 2
    return new Bullet(muzzleX, this.position.y, PLAYER_BULLET_SPEED)
  }
}
