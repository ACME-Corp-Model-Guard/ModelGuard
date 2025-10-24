#!/usr/bin/env python3
"""
Tests for the Authorization class.
"""

import pytest
from src.authorization import Authorization, Permission


class TestAuthorization:
    """Test cases for the Authorization class."""
    
    def test_initialization(self):
        """Test Authorization initialization."""
        auth = Authorization()
        
        assert isinstance(auth.user_permissions, dict)
        assert auth.parameter_store_connection is None
    
    def test_verify_access_no_user(self):
        """Test verifying access for non-existent user."""
        auth = Authorization()
        
        # User should be loaded automatically
        result = auth.verify_access("new_user", Permission.SEARCH)
        assert result is True  # Default permissions are granted
    
    def test_verify_access_existing_user(self):
        """Test verifying access for existing user."""
        auth = Authorization()
        
        # First access should load user permissions
        result1 = auth.verify_access("test_user", Permission.SEARCH)
        assert result1 is True
        
        # Second access should use cached permissions
        result2 = auth.verify_access("test_user", Permission.SEARCH)
        assert result2 is True
    
    def test_grant_permission(self):
        """Test granting permissions."""
        auth = Authorization()
        
        # Grant a permission
        result = auth.grant_permission("test_user", Permission.ADMIN)
        assert result is True
        
        # Verify the permission was granted
        assert Permission.ADMIN in auth.user_permissions["test_user"]
    
    def test_revoke_permission(self):
        """Test revoking permissions."""
        auth = Authorization()
        
        # First grant a permission
        auth.grant_permission("test_user", Permission.UPLOAD)
        assert Permission.UPLOAD in auth.user_permissions["test_user"]
        
        # Then revoke it
        result = auth.revoke_permission("test_user", Permission.UPLOAD)
        assert result is True
        assert Permission.UPLOAD not in auth.user_permissions["test_user"]
    
    def test_revoke_nonexistent_permission(self):
        """Test revoking non-existent permission."""
        auth = Authorization()
        
        # Try to revoke permission for non-existent user
        result = auth.revoke_permission("nonexistent_user", Permission.UPLOAD)
        assert result is False
    
    def test_get_user_permissions(self):
        """Test getting user permissions."""
        auth = Authorization()
        
        # Get permissions for new user (should load defaults)
        permissions = auth.get_user_permissions("new_user")
        assert isinstance(permissions, set)
        assert len(permissions) > 0  # Should have default permissions
    
    def test_is_admin(self):
        """Test admin check."""
        auth = Authorization()
        
        # Regular user should not be admin
        assert auth.is_admin("regular_user") is False
        
        # Grant admin permission
        auth.grant_permission("admin_user", Permission.ADMIN)
        assert auth.is_admin("admin_user") is True
    
    def test_can_upload(self):
        """Test upload permission check."""
        auth = Authorization()
        
        # Default user should have upload permission
        assert auth.can_upload("default_user") is True
        
        # Revoke upload permission
        auth.revoke_permission("default_user", Permission.UPLOAD)
        assert auth.can_upload("default_user") is False
    
    def test_can_search(self):
        """Test search permission check."""
        auth = Authorization()
        
        # Default user should have search permission
        assert auth.can_search("default_user") is True
        
        # Revoke search permission
        auth.revoke_permission("default_user", Permission.SEARCH)
        assert auth.can_search("default_user") is False
    
    def test_can_download(self):
        """Test download permission check."""
        auth = Authorization()
        
        # Default user should have download permission
        assert auth.can_download("default_user") is True
        
        # Revoke download permission
        auth.revoke_permission("default_user", Permission.DOWNLOAD)
        assert auth.can_download("default_user") is False
    
    def test_authenticate_user(self):
        """Test user authentication."""
        auth = Authorization()
        
        # Test with valid credentials
        credentials = {"username": "testuser", "password": "testpass"}
        user_id = auth.authenticate_user(credentials)
        assert user_id == "user_testuser"
        
        # Test with invalid credentials
        invalid_credentials = {"username": "", "password": ""}
        user_id = auth.authenticate_user(invalid_credentials)
        assert user_id is None
        
        # Test with missing credentials
        empty_credentials = {}
        user_id = auth.authenticate_user(empty_credentials)
        assert user_id is None
    
    def test_str_representation(self):
        """Test string representation."""
        auth = Authorization()
        
        str_repr = str(auth)
        assert "Authorization" in str_repr
        assert "users=0" in str_repr
    
    def test_repr_representation(self):
        """Test detailed string representation."""
        auth = Authorization()
        
        repr_str = repr(auth)
        assert "Authorization" in repr_str
        assert "user_permissions=" in repr_str
    
    def test_permission_enum(self):
        """Test Permission enum values."""
        assert Permission.UPLOAD.value == "upload"
        assert Permission.SEARCH.value == "search"
        assert Permission.DOWNLOAD.value == "download"
        assert Permission.ADMIN.value == "admin"
