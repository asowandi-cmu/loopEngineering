/**
 * Integration tests for the SpaceInvaders orchestrator.
 *
 * jsdom does not implement a real 2D canvas context, so we inject a no-op
 * stub: these tests target game *logic* (state transitions, scoring, win/lose
 * resolution) rather than pixels. We drive `update(dt)` directly instead of
 * the RAF loop so each frame is deterministic.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { SpaceInvaders } from '@/game/SpaceInvaders'

/** Minimal CanvasRenderingContext2D stub — every drawing call is a no-op. */
function makeStubContext(): CanvasRenderingContext2D {
  return new Proxy(
    {},
    {
      get: () => () => {},
      set: () => true,
    },
  ) as unknown as CanvasRenderingContext2D
}

function makeCanvas(): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.getContext = (() => makeStubContext()) as HTMLCanvasElement['getContext']
  return canvas
}

/** Simulate pressing and releasing Space once at the window level. */
function tapSpace(): void {
  window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space' }))
  window.dispatchEvent(new KeyboardEvent('keyup', { code: 'Space' }))
}

describe('SpaceInvaders', () => {
  let game: SpaceInvaders

  beforeEach(() => {
    game = new SpaceInvaders(makeCanvas())
  })

  it('starts on the start screen', () => {
    expect(game.getState()).toBe('start')
    expect(game.getScore()).toBe(0)
  })

  it('transitions to playing when Space is pressed', () => {
    tapSpace()
    game.update(0.016)
    expect(game.getState()).toBe('playing')
  })

  it('throws if the 2D context is unavailable', () => {
    const canvas = document.createElement('canvas')
    canvas.getContext = (() => null) as HTMLCanvasElement['getContext']
    expect(() => new SpaceInvaders(canvas)).toThrow()
  })

  it('wins once every alien is destroyed', () => {
    tapSpace()
    game.update(0.016) // enter playing
    // Reach into private grid via a controlled cast to kill all aliens.
    const grid = (game as unknown as { grid: { aliens: { alive: boolean }[] } }).grid
    for (const alien of grid.aliens) alien.alive = false
    game.update(0.016)
    expect(game.getState()).toBe('won')
  })

  it('ends the game when the player is hit', () => {
    tapSpace()
    game.update(0.016) // enter playing
    const player = (game as unknown as { player: { alive: boolean } }).player
    player.alive = false
    game.update(0.016)
    expect(game.getState()).toBe('gameover')
  })

  it('restarts from game over when Space is pressed again', () => {
    tapSpace()
    game.update(0.016)
    const player = (game as unknown as { player: { alive: boolean } }).player
    player.alive = false
    game.update(0.016)
    expect(game.getState()).toBe('gameover')

    tapSpace()
    game.update(0.016)
    expect(game.getState()).toBe('playing')
    expect(game.getScore()).toBe(0)
  })

  it('cleans up without throwing on destroy', () => {
    expect(() => game.destroy()).not.toThrow()
  })

  afterEach(() => {
    game.destroy()
  })
})
