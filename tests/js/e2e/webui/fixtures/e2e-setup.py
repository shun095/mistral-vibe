"""E2E test setup utilities for creating mock data directories and files."""

from __future__ import annotations

import json
import os
from pathlib import Path


def setup_e2e_test_dir() -> Path:
    """Set up a temporary directory for E2E tests with mock data.

    Creates:
    - vibehistory file with sample prompts
    - logs/session directory for session files

    Returns:
        Path to the created test directory
    """
    # Get the test directory from environment or create a temp one
    test_dir = Path(os.getenv("VIBE_E2E_TEST_DIR", "/tmp/vibe-e2e-test"))

    # Clean up any existing test directory
    if test_dir.exists():
        import shutil

        shutil.rmtree(test_dir)

    # Create directory structure
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "logs" / "session").mkdir(parents=True, exist_ok=True)

    # Create mock history file with sample prompts
    history_file = test_dir / "vibehistory"
    sample_prompts = [
        "What is the capital of France?",
        "How do I install Python packages?",
        "Explain the concept of recursion in programming",
        "Write a Python function to reverse a string",
        "What is the difference between list and tuple in Python?",
    ]

    with history_file.open("w", encoding="utf-8") as f:
        for prompt in sample_prompts:
            f.write(f"{prompt}\n")

    return test_dir


def create_mock_session(test_dir: Path, session_id: str = "test-session") -> Path:
    """Create a mock session directory with metadata and messages.

    Args:
        test_dir: The E2E test directory
        session_id: Session ID to use

    Returns:
        Path to the created session directory
    """
    from datetime import UTC, datetime

    session_logs_dir = test_dir / "logs" / "session"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    folder_name = f"session_{timestamp}_{session_id[:8]}"
    session_dir = session_logs_dir / folder_name
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create metadata file
    metadata = {
        "session_id": session_id,
        "title": f"Test Session {session_id[:8]}",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": None,
        "environment": {"working_directory": str(test_dir), "username": "test-user"},
        "agent_profile": None,
        "stats": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": 0,
        },
    }

    with (session_dir / "meta.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Create messages file
    messages = [
        {
            "role": "user",
            "content": "Hello, this is a test message",
            "timestamp": datetime.now(UTC).isoformat(),
        },
        {
            "role": "assistant",
            "content": "Hello! How can I help you today?",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    ]

    with (session_dir / "messages.jsonl").open("w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return session_dir


if __name__ == "__main__":
    # Run as script to test
    test_dir = setup_e2e_test_dir()
    print(f"Created test directory: {test_dir}")
    print(f"Contents: {list(test_dir.rglob('*'))}")
