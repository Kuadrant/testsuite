import pytest


def test_basic(client, auth):
    client.get("/get", auth=auth)
