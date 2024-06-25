"""Tests basic commands"""

import pytest


# https://github.com/Kuadrant/kuadrantctl/issues/90
@pytest.mark.parametrize("command", ["help", "version"])
def test_commands(kuadrantctl, command):
    """Test that basic commands exists and returns anything"""
    result = kuadrantctl.run(command)
    assert not result.stderr, f"Command '{command}' returned an error: {result.stderr}"
    assert result.stdout, f"Command '{command}' returned empty output"
