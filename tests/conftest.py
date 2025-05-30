import pytest

from app import create_app


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    app = create_app()
    return app
