/**
 * Renderer — all canvas drawing for the game.
 *
 * Isolating every `ctx` call here keeps the game logic (SpaceInvaders, the
 * entities) free of rendering concerns and, conversely, keeps the Renderer
 * "dumb": it draws whatever state it's handed and makes no gameplay decisions.
 * That separation is what makes the engine unit-testable without a canvas.
 *
 * Visuals are simple geometric shapes (no sprite assets) so the game is
 * instantly playable with zero asset loading, per the spec.
 */
import type { Alien } from './Alien'
import type { Bullet } from './Bullet'
import type { Player } from './Player'
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  COLORS,
  FONT_FAMILY,
} from './constants'

export class Renderer {
  constructor(private readonly ctx: CanvasRenderingContext2D) {}

  /** Paint the black backdrop, clearing the previous frame. */
  clear(): void {
    this.ctx.fillStyle = COLORS.background
    this.ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
  }

  /** Draw the player as a ship: a body with a raised central cannon. */
  drawPlayer(player: Player): void {
    if (!player.alive) return
    const { x, y } = player.position
    const { width, height } = player.dimensions
    this.ctx.fillStyle = COLORS.player
    // Main hull.
    this.ctx.fillRect(x, y + height / 2, width, height / 2)
    // Cannon turret.
    this.ctx.fillRect(x + width / 2 - 3, y, 6, height / 2)
  }

  /** Draw every living alien; alternate colors by row for visual variety. */
  drawAliens(aliens: Alien[]): void {
    for (const alien of aliens) {
      if (!alien.alive) continue
      this.ctx.fillStyle = alien.row % 2 === 0 ? COLORS.alien : COLORS.alienAlt
      const { x, y } = alien.position
      const { width, height } = alien.dimensions
      // Body.
      this.ctx.fillRect(x, y, width, height)
      // Two "legs" to read as an invader rather than a plain block.
      this.ctx.clearRect(x + width * 0.2, y + height, width * 0.15, 4)
      this.ctx.clearRect(x + width * 0.65, y + height, width * 0.15, 4)
    }
  }

  /** Draw all active bullets, colored by owner (player vs alien). */
  drawBullets(bullets: Bullet[]): void {
    for (const bullet of bullets) {
      if (!bullet.alive) continue
      this.ctx.fillStyle =
        bullet.speed < 0 ? COLORS.playerBullet : COLORS.alienBullet
      this.ctx.fillRect(
        bullet.position.x,
        bullet.position.y,
        bullet.dimensions.width,
        bullet.dimensions.height,
      )
    }
  }

  /** Draw the score in the top-left HUD. */
  drawScore(score: number): void {
    this.ctx.fillStyle = COLORS.text
    this.ctx.font = `16px ${FONT_FAMILY}`
    this.ctx.textAlign = 'left'
    this.ctx.textBaseline = 'top'
    this.ctx.fillText(`SCORE: ${score}`, 12, 12)
  }

  /** Title screen prompting the player to begin. */
  drawStartScreen(): void {
    this.drawCenteredText('SPACE INVADERS', CANVAS_HEIGHT / 2 - 40, 36, COLORS.accent)
    this.drawCenteredText('Press SPACE to start', CANVAS_HEIGHT / 2 + 10, 20, COLORS.text)
    this.drawCenteredText('Move: \u2190 \u2192   Shoot: SPACE', CANVAS_HEIGHT / 2 + 44, 16, COLORS.text)
  }

  /** Game-over screen with final score and restart prompt. */
  drawGameOver(score: number): void {
    this.drawCenteredText('GAME OVER', CANVAS_HEIGHT / 2 - 40, 36, COLORS.alienBullet)
    this.drawCenteredText(`Final score: ${score}`, CANVAS_HEIGHT / 2 + 8, 20, COLORS.text)
    this.drawCenteredText('Press SPACE to play again', CANVAS_HEIGHT / 2 + 44, 16, COLORS.text)
  }

  /** Win screen shown when the entire swarm is destroyed. */
  drawWinScreen(score: number): void {
    this.drawCenteredText('YOU WIN!', CANVAS_HEIGHT / 2 - 40, 36, COLORS.accent)
    this.drawCenteredText(`Final score: ${score}`, CANVAS_HEIGHT / 2 + 8, 20, COLORS.text)
    this.drawCenteredText('Press SPACE to play again', CANVAS_HEIGHT / 2 + 44, 16, COLORS.text)
  }

  /** Helper: horizontally centered text at a given baseline y. */
  private drawCenteredText(text: string, y: number, size: number, color: string): void {
    this.ctx.fillStyle = color
    this.ctx.font = `${size}px ${FONT_FAMILY}`
    this.ctx.textAlign = 'center'
    this.ctx.textBaseline = 'middle'
    this.ctx.fillText(text, CANVAS_WIDTH / 2, y)
  }
}
