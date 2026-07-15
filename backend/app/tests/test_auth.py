from fastapi import status
from fastapi.testclient import TestClient


def test_register_user(client: TestClient) -> None:
    """Tests successful user registration."""
    payload = {"email": "user@example.com", "password": "securepassword"}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "user@example.com"
    assert "id" in data
    assert "hashed_password" not in data  # Assert sensitive password keys are filtered out


def test_register_duplicate_email(client: TestClient) -> None:
    """Asserts registration fails when registering an already registered email."""
    payload = {"email": "user@example.com", "password": "securepassword"}
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == status.HTTP_201_CREATED

    response2 = client.post("/api/v1/auth/register", json=payload)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert response2.json()["detail"] == "A user with this email is already registered"


def test_login_successful(client: TestClient) -> None:
    """Tests successful credentials verification and JWT creation."""
    # 1. Register
    reg_payload = {"email": "login@example.com", "password": "testpassword"}
    client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login (uses form-data username and password)
    login_data = {"username": "login@example.com", "password": "testpassword"}
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient) -> None:
    """Asserts login fails with wrong password."""
    reg_payload = {"email": "login2@example.com", "password": "testpassword"}
    client.post("/api/v1/auth/register", json=reg_payload)

    # Wrong password
    login_data = {"username": "login2@example.com", "password": "wrongpassword"}
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


def test_protected_route_access(client: TestClient) -> None:
    """Verifies that unauthorized requests are blocked and valid JWTs grant access."""
    # 1. Try accessing /me without token
    response_no_token = client.get("/api/v1/auth/me")
    assert response_no_token.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Register and login
    email = "me@example.com"
    password = "password"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    token = login_res.json()["access_token"]

    # 3. Access with valid token header
    headers = {"Authorization": f"Bearer {token}"}
    response_auth = client.get("/api/v1/auth/me", headers=headers)
    assert response_auth.status_code == status.HTTP_200_OK
    assert response_auth.json()["email"] == email
