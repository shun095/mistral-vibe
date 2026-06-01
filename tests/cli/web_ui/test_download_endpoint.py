"""Tests for download endpoint in web UI server."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def app_with_auth():
    """Create test app with authentication."""
    from vibe.cli.web_ui.server import create_app

    # Create a minimal app for testing
    app = create_app(token="test-token")
    return app


@pytest.fixture
def client(app_with_auth):
    """Create test client with auth cookie."""
    return TestClient(app_with_auth, cookies={"vibe_auth": "test-token"})


@pytest.fixture
def test_dir():
    """Create a test subdirectory within the project directory (cwd)."""
    test_dir = Path.cwd() / "download_endpoint_test"
    test_dir.mkdir(exist_ok=True)
    return test_dir


class TestDownloadEndpoint:
    """Test /api/download endpoint."""

    def test_download_text_file(self, client, test_dir):
        """Test downloading a text file."""
        test_file = test_dir / "test.txt"
        test_file.write_text("Hello, World!")

        response = client.get(f"/api/download?file_path={test_file}")

        assert response.status_code == 200
        assert response.content == b"Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert 'filename="test.txt"' in response.headers.get("content-disposition", "")

    def test_download_file_not_found(self, client, test_dir):
        """Test downloading non-existent file within project returns 404."""
        response = client.get(
            f"/api/download?file_path={test_dir / 'does_not_exist.txt'}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    def test_download_outside_project_directory(self, client):
        """Test downloading file outside project directory returns 403."""
        response = client.get("/api/download?file_path=/etc/hosts")

        assert response.status_code == 403
        assert "outside allowed directories" in response.json()["detail"]

    def test_download_directory_returns_400(self, client, test_dir):
        """Test downloading directory returns 400."""
        response = client.get(f"/api/download?file_path={test_dir}")

        assert response.status_code == 400
        assert response.json()["detail"] == "Not a file"

    def test_download_without_auth(self, app_with_auth, test_dir):
        """Test downloading file without authentication returns 401."""
        test_file = test_dir / "test.txt"
        test_file.write_text("Secret content")

        client_no_auth = TestClient(app_with_auth)
        response = client_no_auth.get(f"/api/download?file_path={test_file}")

        assert response.status_code == 401

    def test_download_python_file(self, client, test_dir):
        """Test downloading a Python file."""
        test_file = test_dir / "script.py"
        test_file.write_text("print('Hello')")

        response = client.get(f"/api/download?file_path={test_file}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/x-python; charset=utf-8"

    def test_download_json_file(self, client, test_dir):
        """Test downloading a JSON file."""
        test_file = test_dir / "data.json"
        test_file.write_text('{"key": "value"}')

        response = client.get(f"/api/download?file_path={test_file}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_download_unknown_extension(self, client, test_dir):
        """Test downloading file with unknown extension."""
        test_file = test_dir / "file.unknown"
        test_file.write_text("Unknown type")

        response = client.get(f"/api/download?file_path={test_file}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"

    def test_download_url_encoded_path(self, client, test_dir):
        """Test downloading file with spaces in path."""
        test_file = test_dir / "file with spaces.txt"
        test_file.write_text("Content with spaces")

        # URL encode the path
        import urllib.parse

        encoded_path = urllib.parse.quote(str(test_file))
        response = client.get(f"/api/download?file_path={encoded_path}")

        assert response.status_code == 200
        assert response.content == b"Content with spaces"

    def test_download_symlink(self, client, test_dir):
        """Test downloading a symlink to a file."""
        target_file = test_dir / "target.txt"
        target_file.write_text("Target content")

        link_file = test_dir / "link.txt"
        link_file.symlink_to(target_file)

        response = client.get(f"/api/download?file_path={link_file}")

        assert response.status_code == 200
        assert response.content == b"Target content"
        # Note: FileResponse follows symlinks, so filename will be the target's name
        assert "attachment" in response.headers.get("content-disposition", "")
