def test_basic(client, free_user_auth, paid_user_auth):
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 200

    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 200
