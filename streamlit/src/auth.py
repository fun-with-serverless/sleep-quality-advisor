"""Authentication module for Streamlit app using AWS Secrets Manager."""

import json
import os
import secrets
from typing import Optional

import boto3
import streamlit as st
from botocore.exceptions import ClientError


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def get_credentials_from_secrets_manager() -> dict:
    """
    Retrieve authentication credentials from AWS Secrets Manager.

    Returns:
        dict: Dictionary containing 'username' and 'password' keys

    Raises:
        AuthenticationError: If unable to retrieve credentials
    """
    secret_name = os.getenv("AUTH_SECRET_NAME")
    if not secret_name:
        raise AuthenticationError("AUTH_SECRET_NAME environment variable not set")

    region = os.getenv("AWS_REGION", "us-east-1")

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)

        # Parse the secret value
        if "SecretString" in response:
            secret = json.loads(response["SecretString"])
            return {
                "username": secret.get("username", "admin"),
                "password": secret.get("password", "")
            }
        else:
            raise AuthenticationError("Secret is binary, expected string")

    except ClientError as e:
        raise AuthenticationError(f"Failed to retrieve credentials: {str(e)}")


@st.cache_resource
def load_credentials() -> dict:
    """
    Load and cache credentials from Secrets Manager.
    This is cached to avoid repeated API calls.
    """
    return get_credentials_from_secrets_manager()


def verify_credentials(username: str, password: str) -> bool:
    """
    Verify username and password against stored credentials.
    Uses constant-time comparison to prevent timing attacks.

    Args:
        username: Username to verify
        password: Password to verify

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    try:
        creds = load_credentials()

        # Use constant-time comparison to prevent timing attacks
        username_match = secrets.compare_digest(username, creds["username"])
        password_match = secrets.compare_digest(password, creds["password"])

        return username_match and password_match

    except AuthenticationError as e:
        st.error(f"Authentication error: {str(e)}")
        return False


def login() -> bool:
    """
    Display login form and handle authentication.

    Returns:
        bool: True if user is authenticated, False otherwise
    """
    # Check if user is already authenticated
    if st.session_state.get("authenticated", False):
        return True

    # Display login form
    st.title("🔐 Sleep Quality Advisor")
    st.subheader("Please log in to continue")

    with st.form("login_form"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Login")

        if submit:
            if verify_credentials(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    return False


def logout():
    """Clear authentication state and force logout."""
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.rerun()


def require_authentication(func):
    """
    Decorator to require authentication for a function.
    If user is not authenticated, shows login form instead.
    """
    def wrapper(*args, **kwargs):
        if not st.session_state.get("authenticated", False):
            login()
        else:
            return func(*args, **kwargs)
    return wrapper
