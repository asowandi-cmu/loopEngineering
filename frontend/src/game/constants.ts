/**
 * Tunable game constants for Space Invaders.
 *
 * Why one module: centralising every magic number makes the feel of the game
 * adjustable in a single place and keeps the entity classes declarative.
 *
 * Units: all speeds are expressed in **pixels per second** and all updates take
 * a delta-time (seconds) so motion is frame-rate independent. This avoids the
 * classic bug where the game runs faster on high-refresh displays.
 */

/** Fixed canvas size. The game is designed around these dimensions. */
export const CANVAS_WIDTH = 800
export const CANVAS_HEIGHT = 600

/** Player ship geometry and movement. */
export const PLAYER_WIDTH = 50
export const PLAYER_HEIGHT = 20
export const PLAYER_SPEED = 360 // px/s
/** Gap between the ship and the bottom edge. */
export const PLAYER_BOTTOM_MARGIN = 30
/** Minimum seconds between player shots (rate limit for held Space). */
export const PLAYER_SHOOT_COOLDOWN = 0.35

/** Bullet geometry and speed. Sign of the velocity sets travel direction. */
export const BULLET_WIDTH = 4
export const BULLET_HEIGHT = 12
export const PLAYER_BULLET_SPEED = -480 // negative = upward
export const ALIEN_BULLET_SPEED = 260 // positive = downward

/** Alien formation layout. */
export const ALIEN_ROWS = 5
export const ALIEN_COLS = 11
export const ALIEN_WIDTH = 32
export const ALIEN_HEIGHT = 24
export const ALIEN_H_SPACING = 16 // horizontal gap between aliens
export const ALIEN_V_SPACING = 16 // vertical gap between rows
export const ALIEN_GRID_TOP = 60 // y of the top row at spawn
export const ALIEN_GRID_LEFT = 60 // x of the left column at spawn

/** Alien movement: horizontal march speed and the drop on each edge bounce. */
export const ALIEN_SPEED = 40 // px/s, increases as the swarm thins
export const ALIEN_DESCENT = 20 // px dropped when reversing at an edge
/**
 * Speed multiplier applied per dead alien. The arcade original speeds up as
 * you clear the swarm; we approximate that by scaling march speed with the
 * fraction of aliens destroyed.
 */
export const ALIEN_SPEEDUP_PER_KILL = 0.03

/** Average seconds between alien shots (Poisson-style random firing). */
export const ALIEN_SHOOT_INTERVAL = 1.1

/** Points awarded per alien. Higher rows (closer to the top) are worth more. */
export const ALIEN_POINTS_BY_ROW = [30, 20, 20, 10, 10]

/** Colors (kept here so the Renderer stays purely mechanical). */
export const COLORS = {
  background: '#000000',
  player: '#00ff66',
  playerBullet: '#ffffff',
  alienBullet: '#ff5555',
  alien: '#ffffff',
  alienAlt: '#88ddff',
  text: '#ffffff',
  accent: '#00ff66',
} as const

/** Font stack used for all on-canvas text. */
export const FONT_FAMILY = 'monospace'
