import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test",
            "email": "test_register@example.com",
            "password": "password",
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test",
            "email": "test_register@example.com",
            "password": "password",
        },
    )
    assert response.status_code == 201
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test",
            "email": "test_register@example.com",
            "password": "password",
        },
    )
    data = response.json()
    assert data["detail"] == "username already taken"
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test",
            "email": "test_login@example.com",
            "password": "password",
        },
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "test", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert "token_type" in data


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test",
            "email": "test_login@example.com",
            "password": "password",
        },
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "test", "password": "wrong_password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = login_response.json()
    assert login_response.status_code == 401
    assert data["detail"] == "Invalid username or password"
