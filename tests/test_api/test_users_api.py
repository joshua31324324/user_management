from builtins import str
import pytest
from httpx import AsyncClient
from app.main import app
from app.models.user_model import User, UserRole
from app.utils.nickname_gen import generate_nickname
from app.utils.security import hash_password
from app.services.jwt_service import decode_token  # Import your FastAPI app


from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_user(db_session, email="test@example.com", password="sS#fdasrongPassword123!", role=UserRole.AUTHENTICATED):
    hashed_password = hash_password(password)
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        role=role
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)
    return new_user


@pytest.fixture(scope="function")
async def user(db_session):
    new_user = await create_user(db_session)
    return new_user
@pytest.fixture(scope="function")
async def user_token(user):
    user_instance = await user
    token_data = {"sub": str(user_instance.id), "role": user_instance.role.name}
    token = create_access_token(data=token_data)
    return token

@pytest.fixture(scope="function")
async def admin_user(db_session):
    new_admin = await create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
    return new_admin

@pytest.fixture(scope="function")
async def admin_token(admin_user): 
    admin_instance = await admin_user
    token_data = {"sub": str(admin_instance.id), "role": admin_instance.role.name}
    token = create_access_token(data=token_data)
    return token

@pytest.fixture(scope="function")
async def manager_user(db_session):
    new_manager = await create_user(db_session, email="manager@example.com", role=UserRole.MANAGER)
    return new_manager

@pytest.fixture(scope="function")
async def manager_token(manager_user):
    manager_instance = await manager_user
    token_data = {"sub": str(manager_instance.id), "role": manager_instance.role.name}
    token = create_access_token(data=token_data)
    return token

# Example of a test function using the async_client fixture
@pytest.mark.asyncio
async def test_create_user_access_denied(async_client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    # Define user data for the test
    user_data = {
        "nickname": generate_nickname(),
        "email": "test@example.com",
        "password": "sS#fdasrongPassword123!",
    }
    # Send a POST request to create a user
    response = await async_client.post("/users/", json=user_data, headers=headers)
    # Asserts
    assert response.status_code == 403
@pytest.mark.asyncio
async def test_invalid_professional_status_upgrade(async_client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.put("/api/users/9999/upgrade", headers=headers)
    assert response.status_code == 404
# You can similarly refactor other test functions to use the async_client fixture
@pytest.mark.asyncio
async def test_retrieve_user_access_denied(async_client, verified_user, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await async_client.get(f"/users/{verified_user.id}", headers=headers)
    assert response.status_code == 403
@pytest.mark.asyncio
async def test_retrieve_user_profile(async_client, user):
    response = await async_client.get(f"/api/users/{user.id}")
    assert response.status_code == 200
    retrieved_user = response.json()
    assert retrieved_user["id"] == user.id
@pytest.mark.asyncio
async def test_retrieve_user_access_allowed(async_client, admin_user, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.get(f"/users/{admin_user.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(admin_user.id)

@pytest.mark.asyncio
async def test_update_user_email_access_denied(async_client, verified_user, user_token):
    updated_data = {"email": f"updated_{verified_user.id}@example.com"}
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await async_client.put(f"/users/{verified_user.id}", json=updated_data, headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_update_user_email_access_allowed(async_client, admin_user, admin_token):
    updated_data = {"email": f"updated_{admin_user.id}@example.com"}
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.put(f"/users/{admin_user.id}", json=updated_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == updated_data["email"]

@pytest.mark.asyncio
async def test_update_user_profile_invalid_data(async_client, user):
    user_data = { "name": "", "bio": "New Bio", "location": "Newark, NJ" }
    response = await async_client.put(f"/api/users/{user.id}", json=user_data)
    assert response.status_code == 422
    
@pytest.mark.asyncio
async def test_admin_professional_status_upgrade(async_client, admin_token, regular_user):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.put(f"/api/users/{regular_user.id}/upgrade", headers=headers)
    assert response.status_code == 200
    upgraded_user = response.json()
    assert upgraded_user["role"] == "PROFESSIONAL"
@pytest.mark.asyncio
async def test_admin_upgrade_another_user_profile(async_client, admin_token, regular_user):
    headers = {"Authorization": f"Bearer {admin_token}"}
    user_data = { "name": "Admin Updated Name", "bio": "Admin Updated Bio", "location": "Admin Updated Location" }
    response = await async_client.put(f"/api/users/{regular_user.id}", json=user_data, headers=headers)
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["name"] == "Admin: Updated Name"
    assert updated_user["bio"] == "Admin: Updated Bio"
    assert updated_user["location"] == "Admin: Updated Location"
@pytest.mark.asyncio
async def test_delete_user(async_client, admin_user, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    delete_response = await async_client.delete(f"/users/{admin_user.id}", headers=headers)
    assert delete_response.status_code == 204
    # Verify the user is deleted
    fetch_response = await async_client.get(f"/users/{admin_user.id}", headers=headers)
    assert fetch_response.status_code == 404

@pytest.mark.asyncio
async def test_create_user_duplicate_email(async_client, verified_user):
    user_data = {
        "email": verified_user.email,
        "password": "AnotherPassword123!",
        "role": UserRole.ADMIN.name
    }
    response = await async_client.post("/register/", json=user_data)
    assert response.status_code == 400
    assert "Email already exists" in response.json().get("detail", "")

@pytest.mark.asyncio
async def test_create_user_invalid_email(async_client):
    user_data = {
        "email": "notanemail",
        "password": "ValidPassword123!",
    }
    response = await async_client.post("/register/", json=user_data)
    assert response.status_code == 422

import pytest
from app.services.jwt_service import decode_token
from urllib.parse import urlencode

@pytest.mark.asyncio
async def test_login_success(async_client, verified_user):
    # Attempt to login with the test user
    form_data = {
        "username": verified_user.email,
        "password": "MySuperPassword$1234"
    }
    response = await async_client.post("/login/", data=urlencode(form_data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    # Check for successful login response
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Use the decode_token method from jwt_service to decode the JWT
    decoded_token = decode_token(data["access_token"])
    assert decoded_token is not None, "Failed to decode token"
    assert decoded_token["role"] == "AUTHENTICATED", "The user role should be AUTHENTICATED"

@pytest.mark.asyncio
async def test_login_user_not_found(async_client):
    form_data = {
        "username": "nonexistentuser@here.edu",
        "password": "DoesNotMatter123!"
    }
    response = await async_client.post("/login/", data=urlencode(form_data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 401
    assert "Incorrect email or password." in response.json().get("detail", "")

@pytest.mark.asyncio
async def test_login_incorrect_password(async_client, verified_user):
    form_data = {
        "username": verified_user.email,
        "password": "IncorrectPassword123!"
    }
    response = await async_client.post("/login/", data=urlencode(form_data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 401
    assert "Incorrect email or password." in response.json().get("detail", "")

@pytest.mark.asyncio
async def test_login_unverified_user(async_client, unverified_user):
    form_data = {
        "username": unverified_user.email,
        "password": "MySuperPassword$1234"
    }
    response = await async_client.post("/login/", data=urlencode(form_data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_locked_user(async_client, locked_user):
    form_data = {
        "username": locked_user.email,
        "password": "MySuperPassword$1234"
    }
    response = await async_client.post("/login/", data=urlencode(form_data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 400
    assert "Account locked due to too many failed login attempts." in response.json().get("detail", "")
@pytest.mark.asyncio
async def test_delete_user_does_not_exist(async_client, admin_token):
    non_existent_user_id = "00000000-0000-0000-0000-000000000000"  # Valid UUID format
    headers = {"Authorization": f"Bearer {admin_token}"}
    delete_response = await async_client.delete(f"/users/{non_existent_user_id}", headers=headers)
    assert delete_response.status_code == 404
@pytest.mark.asyncio
async def test_non_admin_professional_status_upgrade_attempt(async_client, user_token, regular_user):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await async_client.put(f"/api/users/{regular_user.id}/upgrade", headers=headers)
    assert response.status_code == 403
    
@pytest.mark.asyncio
async def test_profile_update_missing_required_field(async_client, user):
    user_data = { "bio": "New Bio" }
    response = await async_client.put(f"/api/users/{user.id}", json=user_data)
    assert response.status_code == 422
@pytest.mark.asyncio
async def test_profile_update_with_no_changes(async_client, user):
    user_data = { "name": user.name, "bio": user.bio, "location": user.location }
    response = await async_client.put(f"/api/users/{user.id}", json=user_data)
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["name"] == user.name
@pytest.mark.asyncio
async def test_unauthorized_professional_status_upgrade(async_client):
    response = await async_client.put("/api/users/9999/upgrade")
    assert response.status_code == 401
@pytest.mark.asyncio
async def test_update_user_github(async_client, admin_user, admin_token):
    updated_data = {"github_profile_url": "http://www.github.com/kaw393939"}
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.put(f"/users/{admin_user.id}", json=updated_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["github_profile_url"] == updated_data["github_profile_url"]

@pytest.mark.asyncio
async def test_update_user_linkedin(async_client, admin_user, admin_token):
    updated_data = {"linkedin_profile_url": "http://www.linkedin.com/kaw393939"}
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.put(f"/users/{admin_user.id}", json=updated_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["linkedin_profile_url"] == updated_data["linkedin_profile_url"]

@pytest.mark.asyncio
async def test_list_users_as_admin(async_client, admin_token):
    response = await async_client.get(
        "/users/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert 'items' in response.json()

@pytest.mark.asyncio
async def test_list_users_as_manager(async_client, manager_token):
    response = await async_client.get(
        "/users/",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_list_users_unauthorized(async_client, user_token):
    response = await async_client.get(
        "/users/",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403  # Forbidden, as expected for regular user
