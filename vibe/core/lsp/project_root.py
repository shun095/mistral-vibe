from __future__ import annotations

from pathlib import Path


class ProjectRootFinder:
    """Utility class for finding project roots by walking up the directory tree."""

    @classmethod
    def find_project_root(cls, root_markers: list[str]) -> str:
        """Find the project root by walking up from current directory.

        Args:
            root_markers: List of filenames/directories that indicate a project root

        Returns:
            URI string of the project root directory
        """
        current_dir = Path.cwd()
        max_depth = 100
        depth = 0

        # Walk up the directory tree looking for root markers
        check_dir = current_dir

        while depth <= max_depth:
            # Check if current directory contains any root marker
            for marker in root_markers:
                marker_path = check_dir / marker
                try:
                    if marker_path.exists():
                        # Found a project root, return its URI
                        return str(check_dir.resolve().as_uri())
                except (OSError, PermissionError):
                    continue

            # Move up to parent directory
            try:
                parent = check_dir.parent
                if str(parent) == str(check_dir):
                    # Reached root
                    break
                check_dir = parent
                depth += 1
            except (ValueError, RuntimeError):
                break

        # No project root found, use current directory
        return str(current_dir.resolve().as_uri())
