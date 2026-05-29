/**
 * Unit tests for the framework-agnostic game entities.
 *
 * These cover the spec's stated edge cases that are pure logic (no canvas):
 * player boundary clamping, bullet off-screen pruning, alien swarm reversal,
 * and bottom-of-column firing. Canvas rendering is exercised via E2E instead.
 */
import { describe, it, expect } from 'vitest'
import { Player } from '@/game/Player'
import { Bullet } from '@/game/Bullet'
import { AlienGrid } from '@/game/AlienGrid'
import {
  CANVAS_WIDTH,
  CANVAS_HEIGHT,
  PLAYER_BULLET_SPEED,
  ALIEN_ROWS,
  ALIEN_COLS,
} from '@/game/constants'

describe('Player', () => {
  it('cannot move past the left edge', () => {
    const player = new Player()
    for (let i = 0; i < 100; i++) player.moveLeft(1)
    expect(player.position.x).toBe(0)
  })

  it('cannot move past the right edge', () => {
    const player = new Player()
    for (let i = 0; i < 100; i++) player.moveRight(1)
    expect(player.position.x).toBe(CANVAS_WIDTH - player.dimensions.width)
  })

  it('fires an upward bullet then respects the cooldown', () => {
    const player = new Player()
    const first = player.shoot()
    expect(first).not.toBeNull()
    expect(first!.speed).toBe(PLAYER_BULLET_SPEED)
    // Immediately shooting again is blocked by cooldown.
    expect(player.shoot()).toBeNull()
    // After enough time passes, firing is allowed again.
    player.update(1)
    expect(player.shoot()).not.toBeNull()
  })
})

describe('Bullet', () => {
  it('moves upward with negative speed', () => {
    const bullet = new Bullet(100, 300, -100)
    bullet.update(1)
    expect(bullet.position.y).toBe(200)
    expect(bullet.alive).toBe(true)
  })

  it('dies when it leaves the top of the screen', () => {
    const bullet = new Bullet(100, 5, -100)
    bullet.update(1)
    expect(bullet.alive).toBe(false)
  })

  it('dies when it leaves the bottom of the screen', () => {
    const bullet = new Bullet(100, CANVAS_HEIGHT - 1, 100)
    bullet.update(1)
    expect(bullet.alive).toBe(false)
  })
})

describe('AlienGrid', () => {
  it('spawns a full rows x cols formation', () => {
    const grid = new AlienGrid()
    expect(grid.getAliveAliens().length).toBe(ALIEN_ROWS * ALIEN_COLS)
  })

  it('reverses direction and descends when it hits an edge', () => {
    const grid = new AlienGrid()
    const startY = Math.min(...grid.getAliveAliens().map((a) => a.position.y))

    // March right with a huge dt to slam into the right wall.
    grid.update(100)
    const maxX = Math.max(
      ...grid.getAliveAliens().map((a) => a.position.x + a.dimensions.width),
    )
    expect(maxX).toBeLessThanOrEqual(CANVAS_WIDTH)

    // After bouncing, the swarm should have descended.
    const newY = Math.min(...grid.getAliveAliens().map((a) => a.position.y))
    expect(newY).toBeGreaterThan(startY)
  })

  it('only the frontmost alien in a column may shoot', () => {
    const grid = new AlienGrid()
    const bullet = grid.shoot()
    expect(bullet).not.toBeNull()
    expect(bullet!.speed).toBeGreaterThan(0) // travels downward

    const shooter = grid
      .getAliveAliens()
      .reduce((lowest, a) => (a.position.y > lowest.position.y ? a : lowest))
    // The muzzle x should align with some column's frontmost alien centre.
    const muzzleX = bullet!.position.x
    const matchesAColumnFront = grid.getAliveAliens().some((a) => {
      const front = grid
        .getAliveAliens()
        .filter((o) => o.col === a.col)
        .reduce((lowest, o) => (o.position.y > lowest.position.y ? o : lowest))
      return Math.abs(front.position.x + front.dimensions.width / 2 - muzzleX) < 0.001
    })
    expect(matchesAColumnFront).toBe(true)
    expect(shooter).toBeDefined()
  })

  it('reports cleared once all aliens are dead', () => {
    const grid = new AlienGrid()
    for (const alien of grid.aliens) alien.alive = false
    expect(grid.isCleared()).toBe(true)
  })

  it('detects when the swarm reaches a given y', () => {
    const grid = new AlienGrid()
    expect(grid.reachedBottom(CANVAS_HEIGHT)).toBe(false)
    for (const alien of grid.aliens) alien.position.y = CANVAS_HEIGHT
    expect(grid.reachedBottom(CANVAS_HEIGHT)).toBe(true)
  })
})
