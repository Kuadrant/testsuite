"""Tests basic commands"""

import pytest


@pytest.mark.parametrize("command", ["help", "version"])
def test_commands(kuadrantctl, command):
    """Test that basic commands exist and return anything"""
    result = kuadrantctl.run(command)
    assert not result.stderr, f"Command '{command}' returned an error: {result.stderr}"
    assert result.stdout, f"Command '{command}' returned empty output"


@pytest.mark.parametrize(
    "command",
    [("completion", "bash"), ("completion", "zsh"), ("completion", "fish"), ("completion", "powershell")],
    ids=["bash", "zsh", "fish", "powershell"],
)
def test_completion(kuadrantctl, command):
    """Test that completion commands exist and return anything"""
    result = kuadrantctl.run(*command)
    assert not result.stderr, f"Command '{command}' returned an error: {result.stderr}"
    assert result.stdout, f"Command '{command}' returned empty output"
