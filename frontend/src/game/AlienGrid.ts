/**
 * AlienGrid — owns the swarm formation and its synchronized movement.
 *
 * Centralising movement here (rather than on each `Alien`) is what produces
 * the signature lock-step march: the entire swarm shares one direction and
 * speed, and reverses + descends together the instant *any* living alien
 * touches an edge. Speed scales up as the swarm thins, mirroring the arcade
 * original's rising tension.
 */
import { Alien } from './Alien'
import { Bullet } from './Bullet'
import {
  ALIEN_BULLET_SPEED,
  ALIEN_COLS,
  ALIEN_DESCENT,
  ALIEN_GRID_LEFT,
  ALIEN_GRID_TOP,
  ALIEN_H_SPACING,
  ALIEN_POINTS_BY_ROW,
  ALIEN_ROWS,
  ALIEN_SPEED,
  ALIEN_SPEEDUP_PER_KILL,
  ALIEN_V_SPACING,
  ALIEN_WIDTH,
  ALIEN_HEIGHT,
  CANVAS_WIDTH,
} from './constants'

export class AlienGrid {
  aliens: Alien[] = []
  /** Horizontal march direction: +1 = right, -1 = left. */
  private direction = 1
  /** Total aliens spawned at construction (denominator for speed scaling). */
  private readonly total: number

  constructor() {
    for (let row = 0; row < ALIEN_ROWS; row++) {
      const points = ALIEN_POINTS_BY_ROW[row] ?? 10
      for (let col = 0; col < ALIEN_COLS; col++) {
        const x = ALIEN_GRID_LEFT + col * (ALIEN_WIDTH + ALIEN_H_SPACING)
        const y = ALIEN_GRID_TOP + row * (ALIEN_HEIGHT + ALIEN_V_SPACING)
        this.aliens.push(new Alien(x, y, points, row, col))
      }
    }
    this.total = this.aliens.length
  }

  /** Living aliens, for rendering and collision tests. */
  getAliveAliens(): Alien[] {
    return this.aliens.filter((a) => a.alive)
  }

  /** True once every alien has been destroyed (win condition). */
  isCleared(): boolean {
    return this.getAliveAliens().length === 0
  }

  /**
   * Current march speed in px/s. Scales with the fraction of the swarm killed
   * so the last few aliens skitter quickly.
   */
  private currentSpeed(): number {
    const killed = this.total - this.getAliveAliens().length
    return ALIEN_SPEED * (1 + ALIEN_SPEEDUP_PER_KILL * killed)
  }

  /**
   * March the swarm horizontally; on hitting either edge, reverse and drop.
   *
   * We move first, then measure the swarm's new horizontal extent. If it
   * overshot a wall we nudge it back inside by exactly the overflow, flip
   * direction, and descend — guaranteeing the swarm reverses cleanly at both
   * edges without ever rendering outside the canvas.
   */
  update(dt: number): void {
    const alive = this.getAliveAliens()
    if (alive.length === 0) return

    const dx = this.direction * this.currentSpeed() * dt
    for (const alien of alive) alien.position.x += dx

    let minX = Infinity
    let maxX = -Infinity
    for (const alien of alive) {
      minX = Math.min(minX, alien.position.x)
      maxX = Math.max(maxX, alien.position.x + alien.dimensions.width)
    }

    let overflow = 0
    if (maxX > CANVAS_WIDTH) overflow = CANVAS_WIDTH - maxX // negative
    else if (minX < 0) overflow = -minX // positive

    if (overflow !== 0) {
      for (const alien of alive) {
        alien.position.x += overflow
        alien.position.y += ALIEN_DESCENT
      }
      this.direction *= -1
    }
  }

  /**
   * Pick a random column's frontmost (lowest) living alien and fire downward.
   *
   * Only bottom-of-column aliens may shoot — matching the arcade rule that an
   * invader can't fire through the one beneath it. Returns `null` when the
   * swarm is empty.
   */
  shoot(): Bullet | null {
    const alive = this.getAliveAliens()
    if (alive.length === 0) return null

    // Frontmost alien per column (largest y wins).
    const frontByCol = new Map<number, Alien>()
    for (const alien of alive) {
      const current = frontByCol.get(alien.col)
      if (!current || alien.position.y > current.position.y) {
        frontByCol.set(alien.col, alien)
      }
    }

    const shooters = [...frontByCol.values()]
    const shooter = shooters[Math.floor(Math.random() * shooters.length)]
    const muzzleX = shooter.position.x + shooter.dimensions.width / 2
    const muzzleY = shooter.position.y + shooter.dimensions.height
    return new Bullet(muzzleX, muzzleY, ALIEN_BULLET_SPEED)
  }

  /** True if any living alien's bottom edge has reached `y` (lose condition). */
  reachedBottom(y: number): boolean {
    return this.getAliveAliens().some(
      (a) => a.position.y + a.dimensions.height >= y,
    )
  }
}
