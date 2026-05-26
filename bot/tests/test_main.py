from main import build_app


def test_startup_builds_application():
    """Ensures the application map can be built without syntax or import errors."""
    app = build_app("dummy_test_token")

    # Verify the application compiled and handlers were registered
    assert app is not None
    assert len(app.handlers) > 0
