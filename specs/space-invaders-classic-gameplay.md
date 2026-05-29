# Feature: Space Invaders Classic Gameplay

## Feature Description
A classic Space Invaders arcade game rendered on an HTML5 Canvas using vanilla TypeScript, served as the homepage of the application. The game replaces the existing Hello World demo entirely. Players control a ship at the bottom of the screen, shooting at rows of descending alien invaders. The game features smooth animations, keyboard controls, collision detection, and a local score display. No server-side persistence is needed — this is a pure client-side game delivered via the existing React Islands architecture as a canvas-based island.

## User Story
As a visitor to the application
I want to play a Space Invaders game directly on the homepage
So that I can enjoy a classic arcade experience in my browser

## Problem Statement
The current homepage displays a basic Hello World CRUD demo that has served its purpose as a tutorial scaffold. We need to replace it with a Space Invaders game to demonstrate building interactive canvas-based experiences within the Flask + React Islands architecture.

## Solution Statement
Build a self-contained Space Invaders game using HTML5 Canvas and vanilla TypeScript, mounted as a React Island on the homepage. The game will include:
- A player ship controllable via arrow keys and spacebar
- A grid of alien invaders that move side-to-side and descend
- Bullet mechanics (player shoots up, aliens optionally shoot down)
- Collision detection between bullets and entities
- Game states: start screen, playing, game over
- Local score tracking (in-memory, not persisted)

The existing Hello World model, API routes, controller, schema, frontend components, and tests will be removed.

## Relevant Files
Use these files to implement the feature:

**Backend (modify)**
- `src/app/views/hello.py` — Remove all Hello API routes; simplify to just render the game template
- `src/app/controllers/hello.py` — Remove entirely
- `src/app/models/hello.py` — Remove entirely
- `src/app/schemas/hello.py` — Remove entirely
- `src/app/models/__init__.py` — Remove Hello model import if present
- `src/app/templates/base.html` — Update to mount the game island
- `src/app/__init__.py` — Update blueprint registration if route names change

**Frontend (modify/remove)**
- `frontend/src/islands/hello/index.ts` — Remove
- `frontend/src/components/HelloIsland.tsx` — Remove
- `frontend/src/types/index.ts` — Replace Hello types with game types
- `frontend/src/main.ts` — Update island registry

**Tests (remove/replace)**
- `tests/` — Remove Hello-related tests, add game view test
- `frontend/src/` — Remove Hello component tests if any
- `e2e/hello.spec.ts` — Remove and replace with game E2E test

### New Files
- `src/app/views/game.py` — Simple view blueprint that renders the game page
- `src/app/templates/game.html` — Template extending base with game island mount point
- `frontend/src/islands/game/index.ts` — Island entry point for the game
- `frontend/src/game/SpaceInvaders.ts` — Main game class (game loop, state management)
- `frontend/src/game/Player.ts` — Player ship entity
- `frontend/src/game/Alien.ts` — Alien entity
- `frontend/src/game/AlienGrid.ts` — Manages the alien formation and movement
- `frontend/src/game/Bullet.ts` — Bullet entity (shared by player and aliens)
- `frontend/src/game/Renderer.ts` — Canvas rendering logic
- `frontend/src/game/InputHandler.ts` — Keyboard input management
- `frontend/src/game/types.ts` — Game type definitions (Position, Dimensions, GameState, etc.)
- `frontend/src/game/constants.ts` — Game constants (speeds, sizes, grid layout)
- `frontend/src/components/GameIsland.tsx` — React wrapper that creates canvas and initializes game
- `tests/test_game_view.py` — Backend test for game route
- `e2e/game.spec.ts` — E2E test for game page loading and basic interaction

## Implementation Plan

### Phase 1: Foundation — Remove Hello World & Set Up Game Route
Remove the existing Hello World feature entirely (model, schema, controller, views, frontend components, tests). Create the new game blueprint with a simple route that renders a template containing the canvas island mount point.

### Phase 2: Core Implementation — Build the Game Engine
Implement the Space Invaders game engine in TypeScript:
1. Define types and constants
2. Build entity classes (Player, Alien, Bullet, AlienGrid)
3. Build the input handler for keyboard controls
4. Build the renderer for canvas drawing
5. Build the main game class that ties everything together with a game loop
6. Create the React Island wrapper that initializes the canvas and game

### Phase 3: Integration — Wire Up Islands & Polish
Connect the game island to the main.ts registry, ensure the template mounts it correctly, update the Vite build, and verify everything works end-to-end. Add tests.

## Step by Step Tasks

### Step 1: Remove Hello World Backend
- Delete `src/app/controllers/hello.py`
- Delete `src/app/models/hello.py`
- Delete `src/app/schemas/hello.py`
- Delete `src/app/views/hello.py`
- Remove any Hello model imports from `src/app/models/__init__.py`
- Remove the Hello blueprint registration from `src/app/__init__.py`
- Delete all Hello-related backend tests in `tests/` (e.g., `tests/test_hello.py` or similar)
- Delete the Alembic migration for the hello table (or create a new migration that drops it)

### Step 2: Remove Hello World Frontend
- Delete `frontend/src/islands/hello/index.ts`
- Delete `frontend/src/components/HelloIsland.tsx`
- Remove Hello-related types from `frontend/src/types/index.ts`
- Delete `e2e/hello.spec.ts`
- Remove any Hello-related frontend tests

### Step 3: Create Game Backend Route
- Create `src/app/views/game.py` with a blueprint named `game`:
  - `GET /` — renders `game.html` template
- Create `src/app/templates/game.html` extending `base.html`:
  - Contains a `<div data-island="game"></div>` mount point
  - Page title: "Space Invaders"
- Register the game blueprint in `src/app/__init__.py` at url_prefix `/`
- Create `tests/test_game_view.py` — test that `GET /` returns 200 and contains the game island div

### Step 4: Define Game Types and Constants
- Create `frontend/src/game/types.ts`:
  - `Position { x: number; y: number }`
  - `Dimensions { width: number; height: number }`
  - `GameState = 'start' | 'playing' | 'gameover' | 'won'`
  - `Entity { position: Position; dimensions: Dimensions; alive: boolean }`
- Create `frontend/src/game/constants.ts`:
  - Canvas dimensions (e.g., 800x600)
  - Player speed, bullet speed
  - Alien grid rows/cols (e.g., 5 rows x 11 cols)
  - Alien movement speed, descent amount
  - Alien shoot interval
  - Colors / visual constants

### Step 5: Build Player Entity
- Create `frontend/src/game/Player.ts`:
  - Properties: position, dimensions, speed, alive
  - Methods: `moveLeft()`, `moveRight()`, `shoot()` → returns Bullet
  - Respects canvas boundaries

### Step 6: Build Bullet Entity
- Create `frontend/src/game/Bullet.ts`:
  - Properties: position, dimensions, speed (positive = down, negative = up), alive
  - Methods: `update()` — moves bullet, marks dead if off-screen

### Step 7: Build Alien Entity and AlienGrid
- Create `frontend/src/game/Alien.ts`:
  - Properties: position, dimensions, alive, points
  - Simple data class representing one alien
- Create `frontend/src/game/AlienGrid.ts`:
  - Creates a grid of Aliens based on constants
  - Methods: `update()` — moves all aliens horizontally, reverses direction and descends when hitting edge
  - Method: `shoot()` — randomly selects a bottom-row alive alien to fire
  - Method: `getAliveAliens()` — returns living aliens for rendering/collision

### Step 8: Build Input Handler
- Create `frontend/src/game/InputHandler.ts`:
  - Listens for `keydown`/`keyup` events
  - Tracks currently held keys (ArrowLeft, ArrowRight, Space)
  - Methods: `isLeft()`, `isRight()`, `isShoot()` — return boolean
  - Method: `destroy()` — removes event listeners (cleanup)

### Step 9: Build Renderer
- Create `frontend/src/game/Renderer.ts`:
  - Takes a canvas 2D context
  - Methods:
    - `clear()` — fills background black
    - `drawPlayer(player)` — draws player ship (simple geometric shape)
    - `drawAliens(aliens)` — draws each alive alien
    - `drawBullets(bullets)` — draws all active bullets
    - `drawScore(score)` — draws score text top-left
    - `drawStartScreen()` — "Press SPACE to start"
    - `drawGameOver(score)` — "Game Over" + final score
    - `drawWinScreen(score)` — "You Win!" + final score

### Step 10: Build Main Game Class
- Create `frontend/src/game/SpaceInvaders.ts`:
  - Constructor takes a canvas element
  - Initializes: Player, AlienGrid, InputHandler, Renderer, bullets array, score, game state
  - Game loop using `requestAnimationFrame`:
    - `update()`: process input, move player, update bullets, update aliens, check collisions, check win/lose conditions
    - `render()`: delegate to Renderer based on game state
  - Collision detection:
    - Player bullets hitting aliens → alien dies, score increases
    - Alien bullets hitting player → game over
    - Aliens reaching player's Y position → game over
  - Methods: `start()`, `reset()`, `destroy()` (cleanup)

### Step 11: Create React Island Wrapper
- Create `frontend/src/components/GameIsland.tsx`:
  - React component that renders a `<canvas>` element
  - On mount: creates SpaceInvaders instance, calls `start()`
  - On unmount: calls `destroy()` for cleanup
  - Styles canvas to be centered with appropriate dimensions
- Create `frontend/src/islands/game/index.ts`:
  - Exports the island registration (component + mount function)
- Update `frontend/src/main.ts`:
  - Remove hello island from registry
  - Add game island to registry

### Step 12: Update Frontend Types
- Update `frontend/src/types/index.ts`:
  - Remove all Hello-related types
  - Keep `IslandProps` type or update as needed for game island

### Step 13: Create E2E Test
- Create `e2e/game.spec.ts`:
  - Test: page loads with canvas element visible
  - Test: canvas has correct dimensions
  - Test: pressing Space starts the game (canvas content changes)
  - Test: arrow keys don't cause errors
  - Test: page title contains "Space Invaders"

### Step 14: Run Validation Commands
- Run `script/test` to validate backend and frontend unit tests pass
- Run `script/typecheck` to validate TypeScript and Python types
- Run `script/lint` to validate code style
- Run `script/test-e2e` to validate E2E tests pass

## Testing Strategy

### Unit Tests
- **Backend**: `tests/test_game_view.py` — test GET `/` returns 200, contains `data-island="game"`, has correct title
- **Frontend**: Vitest tests are optional for the game engine since it's canvas-based and hard to unit test meaningfully; E2E provides better coverage for interactive canvas games

### Edge Cases
- Player cannot move beyond canvas left/right boundaries
- Bullets are removed when they leave the canvas (no memory leak)
- Game handles rapid key presses without breaking
- Game loop properly stops on game over / win
- Canvas resizes appropriately or is fixed-size
- Multiple bullets can exist simultaneously
- Alien grid correctly reverses at both edges
- Game can be restarted after game over

## Acceptance Criteria
1. Visiting `/` displays a Space Invaders game on an HTML5 Canvas
2. Player ship moves left/right with arrow keys
3. Player shoots with spacebar; bullets travel upward
4. Aliens are arranged in a grid and move side-to-side, descending periodically
5. Aliens occasionally shoot downward
6. Hitting an alien with a bullet destroys it and increases score
7. Game ends when: player is hit, aliens reach the bottom, or all aliens are destroyed
8. Start screen displays "Press SPACE to start"
9. Game over screen displays final score
10. Win screen displays when all aliens are destroyed
11. All existing Hello World code is fully removed
12. All validation commands pass with zero errors

## Validation Commands
Execute every command to validate the feature works correctly with zero regressions.

```bash
# Ensure dependencies are installed
script/bootstrap

# Run backend + frontend unit tests
script/test

# Run TypeScript and Python type checking
script/typecheck

# Run linting
script/lint

# Run E2E tests (auto-starts dev server)
script/test-e2e
```

## Notes
- The game uses `requestAnimationFrame` for smooth 60fps animation — no `setInterval`
- All game logic is client-side; the Flask backend only serves the HTML page
- The React Island wrapper is thin — it just manages canvas lifecycle. The game engine is pure TypeScript with no React dependency
- Since we're removing the Hello model and its migration, a new Alembic migration should be created to drop the `hellos` table, OR the existing migration file can simply be deleted if we're okay resetting the DB schema
- Future enhancements could include: persistent high scores (would need a new model/API), multiple levels, power-ups, sound effects, mobile touch controls
- The game should be playable immediately — no loading screens or asset downloads needed since we use geometric shapes rather than sprites
