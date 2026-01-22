"""
Prompt Manager Module

Centralized management of all LLM prompts with:
- File-based prompt storage for easy editing
- Version tracking
- Hot-reload capability (no restart needed)
- API endpoints for viewing/editing

Usage:
    from config.prompt_manager import PromptManager

    manager = PromptManager()
    prompt = manager.get_prompt("planner")
    prompt_with_vars = manager.get_prompt("personalization", customer_name="Sarah", ...)
"""
import os
import re
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path


class PromptManager:
    """
    Manages LLM prompts from file-based storage.

    Features:
    - Load prompts from config/prompts/*.txt
    - Variable substitution with {variable_name}
    - Metadata parsing from header comments
    - Hot-reload without restart
    """

    PROMPTS_DIR = Path(__file__).parent / "prompts"

    # Cache for loaded prompts
    _cache: Dict[str, Dict[str, Any]] = {}
    _cache_timestamps: Dict[str, float] = {}

    @classmethod
    def get_prompt(cls, name: str, **variables) -> str:
        """
        Get a prompt by name with optional variable substitution.

        Args:
            name: Prompt name (e.g., "planner", "solver", "personalization")
            **variables: Variables to substitute in the prompt

        Returns:
            Prompt text with variables substituted

        Example:
            prompt = PromptManager.get_prompt(
                "personalization",
                customer_name="Sarah",
                offer_price=499
            )
        """
        prompt_data = cls._load_prompt(name)
        prompt_text = prompt_data["content"]

        # Substitute variables
        for key, value in variables.items():
            prompt_text = prompt_text.replace(f"{{{key}}}", str(value))

        return prompt_text

    @classmethod
    def get_prompt_metadata(cls, name: str) -> Dict[str, Any]:
        """
        Get metadata for a prompt (version, purpose, variables, etc.)

        Returns:
            Dict with version, last_modified, purpose, variables, behavior_notes
        """
        return cls._load_prompt(name)["metadata"]

    @classmethod
    def list_prompts(cls) -> Dict[str, Dict[str, Any]]:
        """
        List all available prompts with their metadata.

        Returns:
            Dict mapping prompt names to their metadata
        """
        prompts = {}
        for file_path in cls.PROMPTS_DIR.glob("*.txt"):
            name = file_path.stem
            try:
                prompt_data = cls._load_prompt(name)
                prompts[name] = {
                    "name": name,
                    "file": str(file_path),
                    "metadata": prompt_data["metadata"],
                    "content_preview": prompt_data["content"][:200] + "..."
                }
            except Exception as e:
                prompts[name] = {"name": name, "error": str(e)}
        return prompts

    @classmethod
    def update_prompt(cls, name: str, content: str) -> Dict[str, Any]:
        """
        Update a prompt file with new content.

        Args:
            name: Prompt name
            content: New prompt content

        Returns:
            Dict with success status and metadata
        """
        file_path = cls.PROMPTS_DIR / f"{name}.txt"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt '{name}' not found")

        # Read existing content to preserve metadata header format
        with open(file_path, 'r') as f:
            existing = f.read()

        # Update version in header
        lines = content.split('\n')
        updated_lines = []
        for line in lines:
            if line.startswith('# Version:'):
                # Increment version
                match = re.search(r'Version:\s*(\d+)\.(\d+)', line)
                if match:
                    major, minor = int(match.group(1)), int(match.group(2))
                    updated_lines.append(f'# Version: {major}.{minor + 1}')
                else:
                    updated_lines.append(line)
            elif line.startswith('# Last Modified:'):
                updated_lines.append(f'# Last Modified: {datetime.now().strftime("%Y-%m-%d")}')
            else:
                updated_lines.append(line)

        new_content = '\n'.join(updated_lines)

        # Write updated content
        with open(file_path, 'w') as f:
            f.write(new_content)

        # Clear cache
        if name in cls._cache:
            del cls._cache[name]

        return {
            "success": True,
            "name": name,
            "message": f"Prompt '{name}' updated successfully",
            "new_metadata": cls.get_prompt_metadata(name)
        }

    @classmethod
    def _load_prompt(cls, name: str) -> Dict[str, Any]:
        """Load prompt from file with caching and hot-reload."""
        file_path = cls.PROMPTS_DIR / f"{name}.txt"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        # Check if cache is valid
        file_mtime = file_path.stat().st_mtime
        if name in cls._cache and cls._cache_timestamps.get(name, 0) >= file_mtime:
            return cls._cache[name]

        # Load and parse prompt
        with open(file_path, 'r') as f:
            content = f.read()

        metadata = cls._parse_metadata(content)
        prompt_content = cls._extract_content(content)

        prompt_data = {
            "content": prompt_content,
            "metadata": metadata,
            "file_path": str(file_path)
        }

        # Update cache
        cls._cache[name] = prompt_data
        cls._cache_timestamps[name] = file_mtime

        return prompt_data

    @classmethod
    def _parse_metadata(cls, content: str) -> Dict[str, Any]:
        """Parse metadata from header comments."""
        metadata = {
            "version": "1.0",
            "last_modified": None,
            "purpose": None,
            "variables": [],
            "behavior_notes": []
        }

        lines = content.split('\n')
        in_header = True
        current_section = None

        for line in lines:
            if not line.startswith('#'):
                if in_header and line.strip():
                    in_header = False
                continue

            line = line[1:].strip()  # Remove # prefix

            if line.startswith('Version:'):
                metadata["version"] = line.split(':', 1)[1].strip()
            elif line.startswith('Last Modified:'):
                metadata["last_modified"] = line.split(':', 1)[1].strip()
            elif line.startswith('Purpose:'):
                metadata["purpose"] = line.split(':', 1)[1].strip()
            elif line.startswith('Variables available:'):
                current_section = "variables"
            elif line.startswith('How changes affect behavior:'):
                current_section = "behavior_notes"
            elif line.startswith('  - ') and current_section:
                if current_section == "variables":
                    metadata["variables"].append(line[4:])
                elif current_section == "behavior_notes":
                    metadata["behavior_notes"].append(line[4:])

        return metadata

    @classmethod
    def _extract_content(cls, content: str) -> str:
        """Extract prompt content (everything after header comments)."""
        lines = content.split('\n')
        content_lines = []
        header_ended = False

        for line in lines:
            if not header_ended:
                if not line.startswith('#') and line.strip():
                    header_ended = True
                    content_lines.append(line)
            else:
                content_lines.append(line)

        return '\n'.join(content_lines).strip()


# Convenience functions for direct import
def get_prompt(name: str, **variables) -> str:
    """Get a prompt by name with variable substitution."""
    return PromptManager.get_prompt(name, **variables)


def list_prompts() -> Dict[str, Dict[str, Any]]:
    """List all available prompts."""
    return PromptManager.list_prompts()


def update_prompt(name: str, content: str) -> Dict[str, Any]:
    """Update a prompt."""
    return PromptManager.update_prompt(name, content)
