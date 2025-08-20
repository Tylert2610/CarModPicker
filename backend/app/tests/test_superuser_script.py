import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.dependencies.auth import get_password_hash
from app.tests.conftest import db_session


class TestSuperuserCreation:
    """Test cases for superuser creation functionality."""

    def test_create_superuser_success(self, db_session: Session):
        """Test successful superuser creation."""
        from scripts.create_superuser import create_superuser

        # Test data
        username = "test_superuser"
        email = "test_superuser@example.com"
        password = "testpassword123"
        is_superuser = True
        is_admin = True

        # Create superuser
        result = create_superuser(username, email, password, is_superuser, is_admin)

        # Verify the superuser was created
        assert result is not None
        assert result.username == username
        assert result.email == email
        assert result.is_superuser == is_superuser
        assert result.is_admin == is_admin
        assert result.email_verified == True  # Auto-verified for superusers
        assert result.disabled == False

        # Verify password was hashed
        assert result.hashed_password != password
        assert result.hashed_password != ""

        # Verify user exists in database
        db_user = db_session.query(DBUser).filter(DBUser.username == username).first()
        assert db_user is not None
        assert db_user.id == result.id

    def test_create_admin_user_success(self, db_session: Session):
        """Test successful admin user creation (not superuser)."""
        from scripts.create_superuser import create_superuser

        # Test data
        username = "test_admin"
        email = "test_admin@example.com"
        password = "testpassword123"
        is_superuser = False
        is_admin = True

        # Create admin user
        result = create_superuser(username, email, password, is_superuser, is_admin)

        # Verify the admin user was created
        assert result is not None
        assert result.username == username
        assert result.email == email
        assert result.is_superuser == is_superuser
        assert result.is_admin == is_admin
        assert result.email_verified == True
        assert result.disabled == False

    def test_create_superuser_duplicate_username(self, db_session: Session):
        """Test that creating superuser with duplicate username returns existing user."""
        from scripts.create_superuser import create_superuser

        # Create first superuser
        username = "duplicate_test"
        email1 = "test1@example.com"
        password = "testpassword123"

        user1 = create_superuser(username, email1, password, True, True)
        assert user1 is not None

        # Try to create second superuser with same username
        email2 = "test2@example.com"
        user2 = create_superuser(username, email2, password, True, True)

        # Should return the existing user
        assert user2 is not None
        assert user2.id == user1.id
        assert user2.username == user1.username
        assert user2.email == user1.email  # Should be the original email

    def test_create_superuser_duplicate_email(self, db_session: Session):
        """Test that creating superuser with duplicate email returns existing user."""
        from scripts.create_superuser import create_superuser

        # Create first superuser
        username1 = "test1"
        email = "duplicate@example.com"
        password = "testpassword123"

        user1 = create_superuser(username1, email, password, True, True)
        assert user1 is not None

        # Try to create second superuser with same email
        username2 = "test2"
        user2 = create_superuser(username2, email, password, True, True)

        # Should return the existing user
        assert user2 is not None
        assert user2.id == user1.id
        assert user2.username == user1.username
        assert user2.email == user1.email

    def test_create_superuser_password_hashing(self, db_session: Session):
        """Test that passwords are properly hashed."""
        from scripts.create_superuser import create_superuser
        from app.api.dependencies.auth import verify_password

        # Test data
        username = "password_test"
        email = "password_test@example.com"
        password = "testpassword123"
        is_superuser = True
        is_admin = True

        # Create superuser
        result = create_superuser(username, email, password, is_superuser, is_admin)

        # Verify password was hashed
        assert result.hashed_password != password
        assert len(result.hashed_password) > 0

        # Verify password can be verified
        assert verify_password(password, result.hashed_password) == True

        # Verify wrong password fails
        assert verify_password("wrongpassword", result.hashed_password) == False

    def test_create_superuser_default_values(self, db_session: Session):
        """Test that default values are set correctly."""
        from scripts.create_superuser import create_superuser

        # Test data
        username = "default_test"
        email = "default_test@example.com"
        password = "testpassword123"

        # Create superuser with defaults
        result = create_superuser(username, email, password)

        # Verify default values
        assert result.is_superuser == True  # Default
        assert result.is_admin == True  # Default
        assert result.email_verified == True  # Auto-verified for superusers
        assert result.disabled == False

    def test_create_superuser_custom_values(self, db_session: Session):
        """Test that custom values override defaults."""
        from scripts.create_superuser import create_superuser

        # Test data
        username = "custom_test"
        email = "custom_test@example.com"
        password = "testpassword123"
        is_superuser = False
        is_admin = True

        # Create user with custom values
        result = create_superuser(username, email, password, is_superuser, is_admin)

        # Verify custom values were used
        assert result.is_superuser == is_superuser
        assert result.is_admin == is_admin
        assert result.email_verified == True  # Still auto-verified
        assert result.disabled == False

    def test_create_superuser_database_rollback(self, db_session: Session):
        """Test that database rollback works on error."""
        from scripts.create_superuser import create_superuser

        # Create a user first
        username1 = "rollback_test1"
        email1 = "rollback_test1@example.com"
        password = "testpassword123"

        user1 = create_superuser(username1, email1, password, True, True)
        original_count = db_session.query(DBUser).count()

        # Try to create a user with duplicate username (should fail and rollback)
        username2 = username1  # Duplicate username
        email2 = "rollback_test2@example.com"

        # This should not raise an exception, but return the existing user
        user2 = create_superuser(username2, email2, password, True, True)

        # Verify no new user was created
        final_count = db_session.query(DBUser).count()
        assert final_count == original_count

        # Verify we got the original user back
        assert user2.id == user1.id

    def test_superuser_script_imports(self):
        """Test that the superuser script can be imported without errors."""
        try:
            import scripts.create_superuser

            assert True, "Superuser script imports successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import superuser script: {e}")

    def test_superuser_script_functions_exist(self):
        """Test that required functions exist in the superuser script."""
        import scripts.create_superuser

        # Check that required functions exist
        assert hasattr(scripts.create_superuser, "create_superuser")
        assert hasattr(scripts.create_superuser, "main")
        assert callable(scripts.create_superuser.create_superuser)
        assert callable(scripts.create_superuser.main)

    @patch("builtins.input")
    @patch("builtins.print")
    def test_superuser_script_main_function(self, mock_print, mock_input):
        """Test the main function of the superuser script."""
        from scripts.create_superuser import main

        # Mock user input
        mock_input.side_effect = [
            "test_user",  # username
            "test@example.com",  # email
            "testpassword",  # password
            "testpassword",  # confirm password
            "y",  # make superuser
            "y",  # make admin
            "y",  # confirm
        ]

        # Mock the create_superuser function to avoid database operations
        with patch("scripts.create_superuser.create_superuser") as mock_create:
            mock_user = MagicMock()
            mock_user.username = "test_user"
            mock_user.email = "test@example.com"
            mock_create.return_value = mock_user

            # Call main function
            main()

            # Verify create_superuser was called with correct arguments
            mock_create.assert_called_once_with(
                "test_user", "test@example.com", "testpassword", True, True
            )

    @patch("builtins.input")
    @patch("builtins.print")
    def test_superuser_script_main_function_cancelled(self, mock_print, mock_input):
        """Test that main function can be cancelled."""
        from scripts.create_superuser import main

        # Mock user input to cancel
        mock_input.side_effect = [
            "test_user",  # username
            "test@example.com",  # email
            "testpassword",  # password
            "testpassword",  # confirm password
            "y",  # make superuser
            "y",  # make admin
            "n",  # cancel
        ]

        # Mock the create_superuser function
        with patch("scripts.create_superuser.create_superuser") as mock_create:
            # Call main function
            main()

            # Verify create_superuser was NOT called
            mock_create.assert_not_called()

    @patch("builtins.input")
    @patch("builtins.print")
    def test_superuser_script_main_function_password_mismatch(
        self, mock_print, mock_input
    ):
        """Test that main function handles password mismatch."""
        from scripts.create_superuser import main

        # Mock user input with password mismatch
        mock_input.side_effect = [
            "test_user",  # username
            "test@example.com",  # email
            "testpassword",  # password
            "differentpassword",  # confirm password (different)
        ]

        # Mock the create_superuser function
        with patch("scripts.create_superuser.create_superuser") as mock_create:
            # Call main function
            main()

            # Verify create_superuser was NOT called
            mock_create.assert_not_called()

    @patch("builtins.input")
    @patch("builtins.print")
    def test_superuser_script_main_function_no_privileges(self, mock_print, mock_input):
        """Test that main function requires at least admin privileges."""
        from scripts.create_superuser import main

        # Mock user input with no privileges
        mock_input.side_effect = [
            "test_user",  # username
            "test@example.com",  # email
            "testpassword",  # password
            "testpassword",  # confirm password
            "n",  # make superuser (no)
            "n",  # make admin (no)
        ]

        # Mock the create_superuser function
        with patch("scripts.create_superuser.create_superuser") as mock_create:
            # Call main function
            main()

            # Verify create_superuser was NOT called
            mock_create.assert_not_called()
