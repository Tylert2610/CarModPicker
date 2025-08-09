from app.api.dependencies.auth import get_password_hash, verify_password
from app.api.dependencies.auth import create_access_token, ALGORITHM
from app.core.config import settings
from jose import jwt
from datetime import timedelta, datetime, timezone

def test_get_password_hash():
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password is not None
    assert isinstance(hashed_password, str)
    assert hashed_password != password

def test_verify_password_correct():
    password = "testpassword123"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password) is True

def test_verify_password_incorrect():
    password = "testpassword123"
    wrong_password = "wrongpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(wrong_password, hashed_password) is False

def test_verify_password_with_different_hashes():
    password = "anotherpassword"
    hashed1 = get_password_hash(password)
    hashed2 = get_password_hash(password) # bcrypt generates different salts
    assert hashed1 != hashed2
    assert verify_password(password, hashed1) is True
    assert verify_password(password, hashed2) is True

def test_create_access_token():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    assert token is not None
    assert isinstance(token, str)

    # Decode token to check payload
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser"
    assert "exp" in payload
    
    # Check default expiration
    expected_exp_datetime = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    actual_exp_datetime = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    # Allow a small delta for execution time
    assert abs((expected_exp_datetime - actual_exp_datetime).total_seconds()) < 5 

def test_create_access_token_custom_expiry():
    data = {"sub": "testuser_custom_exp"}
    custom_delta = timedelta(minutes=10)
    token = create_access_token(data, expires_delta=custom_delta)
    
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser_custom_exp"
    
    expected_exp_datetime = datetime.now(timezone.utc) + custom_delta
    actual_exp_datetime = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert abs((expected_exp_datetime - actual_exp_datetime).total_seconds()) < 5