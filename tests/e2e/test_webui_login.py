"""E2E tests for WebUI login functionality using Playwright."""

from __future__ import annotations

from collections.abc import Generator

from playwright.sync_api import Page, sync_playwright
import pytest

from tests.e2e.conftest import WebUIServer


@pytest.fixture
def page() -> Generator[Page, None, None]:
    """Create a Playwright page for testing."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def test_login_page_loads(page: Page, webui_server: WebUIServer) -> None:
    """Test that login page loads when not authenticated."""
    # Navigate to root - should redirect to login
    page.goto(f"http://127.0.0.1:{webui_server.port}/")

    # Should be redirected to login page
    assert page.url.endswith("/login")
    assert "Mistral Vibe - Login" in page.title()
    assert "Authentication Token" in page.inner_text("body")


def test_login_with_valid_token(page: Page, webui_server: WebUIServer) -> None:
    """Test successful login with valid token."""
    # Navigate to login page
    page.goto(f"http://127.0.0.1:{webui_server.port}/login")

    # Enter valid token
    page.fill("#token", "test-token")
    page.click("#login-btn")

    # Should be redirected to chat page
    page.wait_for_url(f"http://127.0.0.1:{webui_server.port}/")

    # Verify chat page elements are present
    assert page.is_visible("#messages")  # Messages container
    assert page.is_visible("#message-input")  # Message input textarea
    assert page.is_visible("#send-btn")  # Send button
    assert page.is_visible("#status")  # Connection status


def test_login_with_invalid_token(page: Page, webui_server: WebUIServer) -> None:
    """Test login failure with invalid token."""
    # Navigate to login page
    page.goto(f"http://127.0.0.1:{webui_server.port}/login")

    # Enter invalid token
    page.fill("#token", "invalid-token")
    page.click("#login-btn")

    # Should stay on login page and show error
    assert page.url.endswith("/login")

    # Wait for error message to appear
    error_msg = page.wait_for_selector("#error-message", timeout=5000)
    assert error_msg is not None
    assert "Invalid" in error_msg.inner_text()


def test_logout_button(page: Page, webui_server: WebUIServer) -> None:
    """Test logout button exists after login."""
    # First login
    page.goto(f"http://127.0.0.1:{webui_server.port}/login")
    page.fill("#token", "test-token")
    page.click("#login-btn")

    # Wait for main page to load by checking for the logout button
    page.wait_for_selector("#logout-btn", state="visible", timeout=15000)

    # Verify we're on the main page
    assert page.url.endswith("/")

    # Verify logout button is visible
    logout_btn = page.locator("#logout-btn")
    assert logout_btn.is_visible()


def test_protected_endpoint_requires_auth(
    page: Page, webui_server: WebUIServer
) -> None:
    """Test that protected endpoints redirect to login without auth."""
    # Try to access main page without auth
    page.goto(f"http://127.0.0.1:{webui_server.port}/")

    # Should be redirected to login
    assert page.url.endswith("/login")


def test_health_endpoint_no_auth(page: Page, webui_server: WebUIServer) -> None:
    """Test that health endpoint is accessible without authentication."""
    # Navigate to health endpoint
    page.goto(f"http://127.0.0.1:{webui_server.port}/health")

    # Should succeed without redirect
    assert page.url.endswith("/health")
