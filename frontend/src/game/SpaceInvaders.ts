/**
 * SpaceInvaders — the game orchestrator.
 *
 * Owns every subsystem (Player, AlienGrid, InputHandler, Renderer, the bullet
 * pool, score, and lifecycle state) and drives them from a single
 * `requestAnimationFrame` loop. Centralising the loop here is what guarantees
 * a consistent update→collide→render order each frame and a single place to
 * stop simulation on win/lose.
 *
 * Frame-rate independence: the loop computes a delta-time in seconds and feeds
 * it to every `update(dt)`, so the game plays identically at 30, 60, or 144Hz.
 * The first frame's dt is clamped to avoid a giant jump after tab refocus.
 */
import { AlienGrid } from './AlienGrid'
import { Bullet } from './Bullet'
import { InputHandler } from './InputHandler'
import { Player } from './Player'
import { Renderer } from './Renderer'
import type { Entity, GameState } from './types'
import {
  ALIEN_SHOOT_INTERVAL,
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
} from './constants'

/** Axis-aligned bounding-box overlap test between two entities. */
function intersects(a: Entity, b: Entity): boolean {
  return (
    a.position.x < b.position.x + b.dimensions.width &&
    a.position.x + a.dimensions.width > b.position.x &&
    a.position.y < b.position.y + b.dimensions.height &&
    a.position.y + a.dimensions.height > b.position.y
  )
}

export class SpaceInvaders {
  private readonly ctx: CanvasRenderingContext2D
  private readonly renderer: Renderer
  private readonly input: InputHandler

  private player!: Player
  private grid!: AlienGrid
  private bullets: Bullet[] = []
  private score = 0
  private state: GameState = 'start'

  /** Countdown (seconds) until the swarm next fires. */
  private alienShootTimer = ALIEN_SHOOT_INTERVAL
  /** Timestamp of the previous animation frame (ms), or null before start. */
  private lastTime: number | null = null
  /** Active RAF handle, or null when the loop is stopped. */
  private rafId: number | null = null

  constructor(canvas: HTMLCanvasElement) {
    canvas.width = CANVAS_WIDTH
    canvas.height = CANVAS_HEIGHT

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('SpaceInvaders: 2D canvas context is not available')
    }
    this.ctx = ctx
    this.renderer = new Renderer(this.ctx)
    this.input = new InputHandler(window)

    // Make the canvas keyboard-focusable so it can be tabbed to; input is
    // captured at the window level, but focusability aids accessibility/E2E.
    if (!canvas.hasAttribute('tabindex')) canvas.tabIndex = 0

    this.reset()
  }

  /** Reset all gameplay state to the start of a fresh round. */
  reset(): void {
    this.player = new Player()
    this.grid = new AlienGrid()
    this.bullets = []
    this.score = 0
    this.alienShootTimer = ALIEN_SHOOT_INTERVAL
  }

  /** Begin the animation loop. Idempotent: re-entry won't stack RAF loops. */
  start(): void {
    if (this.rafId !== null) return
    this.lastTime = null
    this.rafId = requestAnimationFrame(this.loop)
  }

  /** Stop the loop and tear down listeners. Call on unmount to avoid leaks. */
  destroy(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId)
      this.rafId = null
    }
    this.input.destroy()
  }

  /** Read-only accessors, primarily for tests/diagnostics. */
  getState(): GameState {
    return this.state
  }

  getScore(): number {
    return this.score
  }

  private loop = (now: number): void => {
    // Convert ms→s and clamp the first/after-stall frame so motion never
    // teleports (e.g. when the tab was backgrounded).
    const dt = this.lastTime === null ? 0 : Math.min((now - this.lastTime) / 1000, 0.05)
    this.lastTime = now

    this.update(dt)
    this.render()

    this.rafId = requestAnimationFrame(this.loop)
  }

  /**
   * Advance the simulation by `dt` seconds.
   *
   * Menu states (start/gameover/won) only watch for a Space press to begin a
   * new round; only `playing` runs the full simulation and collision pass.
   */
  update(dt: number): void {
    if (this.state !== 'playing') {
      if (this.input.consumeStart()) {
        this.reset()
        this.state = 'playing'
      }
      return
    }

    // --- Player movement & firing -----------------------------------------
    this.player.update(dt)
    if (this.input.isLeft()) this.player.moveLeft(dt)
    if (this.input.isRight()) this.player.moveRight(dt)
    if (this.input.isShoot()) {
      const bullet = this.player.shoot()
      if (bullet) this.bullets.push(bullet)
    }

    // --- Swarm movement & firing ------------------------------------------
    this.grid.update(dt)
    this.alienShootTimer -= dt
    if (this.alienShootTimer <= 0) {
      const bullet = this.grid.shoot()
      if (bullet) this.bullets.push(bullet)
      // Randomise the next interval around the configured average.
      this.alienShootTimer = ALIEN_SHOOT_INTERVAL * (0.5 + Math.random())
    }

    // --- Bullet movement & pruning ----------------------------------------
    for (const bullet of this.bullets) bullet.update(dt)

    this.handleCollisions()

    // Drop dead bullets so the array can't grow without bound (memory leak).
    this.bullets = this.bullets.filter((b) => b.alive)

    // --- Win / lose checks -------------------------------------------------
    if (this.grid.isCleared()) {
      this.state = 'won'
    } else if (
      this.grid.reachedBottom(this.player.position.y) ||
      !this.player.alive
    ) {
      this.state = 'gameover'
    }
  }

  /**
   * Resolve bullet collisions for the frame.
   *
   * Player bullets (upward) destroy aliens and score points; alien bullets
   * (downward) kill the player. A bullet is consumed (`alive = false`) on its
   * first hit so it can't pierce multiple targets in one frame.
   */
  private handleCollisions(): void {
    for (const bullet of this.bullets) {
      if (!bullet.alive) continue

      if (bullet.speed < 0) {
        // Player bullet vs aliens.
        for (const alien of this.grid.getAliveAliens()) {
          if (intersects(bullet, alien)) {
            alien.alive = false
            bullet.alive = false
            this.score += alien.points
            break
          }
        }
      } else if (this.player.alive && intersects(bullet, this.player)) {
        // Alien bullet vs player.
        this.player.alive = false
        bullet.alive = false
      }
    }
  }

  /** Render the current frame according to game state. */
  private render(): void {
    this.renderer.clear()

    switch (this.state) {
      case 'start':
        this.renderer.drawStartScreen()
        break
      case 'playing':
        this.renderer.drawAliens(this.grid.getAliveAliens())
        this.renderer.drawBullets(this.bullets)
        this.renderer.drawPlayer(this.player)
        this.renderer.drawScore(this.score)
        break
      case 'gameover':
        this.renderer.drawScore(this.score)
        this.renderer.drawGameOver(this.score)
        break
      case 'won':
        this.renderer.drawScore(this.score)
        this.renderer.drawWinScreen(this.score)
        break
    }
  }
}

export { CANVAS_WIDTH, CANVAS_HEIGHT }
