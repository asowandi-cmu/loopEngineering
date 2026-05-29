/**
 * GameIsland — thin React wrapper that owns the canvas lifecycle.
 *
 * Per the spec, the game engine is pure TypeScript with no React dependency;
 * this component's *only* jobs are to render a `<canvas>` and to bind the
 * engine's lifecycle to React's: create + `start()` on mount, `destroy()` on
 * unmount. Keeping React out of the game loop avoids re-render churn and keeps
 * the engine portable.
 */
import { useEffect, useRef } from 'react'
import { SpaceInvaders, CANVAS_WIDTH, CANVAS_HEIGHT } from '@/game/SpaceInvaders'

export function GameIsland() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const game = new SpaceInvaders(canvas)
    game.start()

    // Cleanup cancels the RAF loop and removes key listeners, so navigating
    // away or hot-reloading never leaks a running game or global handlers.
    return () => game.destroy()
  }, [])

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_WIDTH}
      height={CANVAS_HEIGHT}
      aria-label="Space Invaders game"
      className="border border-gray-700 rounded-lg shadow-lg bg-black max-w-full"
    />
  )
}
