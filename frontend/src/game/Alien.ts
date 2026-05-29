/**
 * Alien entity — a single invader.
 *
 * Intentionally a thin data class: it holds position/size/alive/points but no
 * behaviour. All movement is orchestrated by `AlienGrid` so the whole swarm
 * stays in lock-step (the defining feel of Space Invaders), which would be
 * impossible if each alien moved itself independently.
 */
import type { Dimensions, Entity, Position } from './types'
import { ALIEN_HEIGHT, ALIEN_WIDTH } from './constants'

export class Alien implements Entity {
  position: Position
  dimensions: Dimensions
  alive = true
  /** Score awarded when this alien is destroyed. */
  points: number
  /** Grid row index (0 = top). Used for sprite variation and point values. */
  row: number
  /** Grid column index (0 = left). Used to find the bottom alien per column. */
  col: number

  constructor(x: number, y: number, points: number, row: number, col: number) {
    this.position = { x, y }
    this.dimensions = { width: ALIEN_WIDTH, height: ALIEN_HEIGHT }
    this.points = points
    this.row = row
    this.col = col
  }
}
