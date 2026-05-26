from config import BotConfig
from main import build_app


def test_startup_builds_application():
    """Ensures the application map can be built without syntax or import errors."""
    config = BotConfig(
        token="dummy_test_token",
        api_base_url="http://fake.local/api/",
        persistence_path="/tmp/test_bot_state.pickle",
    )
    app = build_app(config)

    # Verify the application compiled and handlers were registered
    assert app is not None
    assert len(app.handlers) > 0
