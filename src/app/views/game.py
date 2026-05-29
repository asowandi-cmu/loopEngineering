"""Game view (route).

Serves the Space Invaders game homepage. The game itself is a pure
client-side TypeScript engine mounted as a React Island; the backend
only needs to render the HTML shell that contains the island mount point.

There is intentionally no database access or API surface here — the game
is entirely client-side with in-memory score tracking (see the spec's
"no server-side persistence" requirement).
"""
from flask import Blueprint, render_template

game_bp = Blueprint('game', __name__)


@game_bp.route('/')
def index():  # type: ignore[no-untyped-def]
    """Render the Space Invaders game page.

    Serves HTML containing a ``[data-island="game"]`` mount point that the
    frontend hydrates with the canvas-based game on the client.
    """
    return render_template('game.html')
