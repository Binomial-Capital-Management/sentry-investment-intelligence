"""
Clerk Backend API Client
Makes authenticated requests to Clerk's REST API for organization management.

Following CODING_RULES.md: KISS, no hardcoding, evidence-based implementation
Based on Clerk API documentation: https://clerk.com/docs
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from core.config import get_config

logger = logging.getLogger(__name__)


class ClerkClient:
    """
    Client for Clerk Backend API.
    Handles organization invitations and member management.
    """

    def __init__(self):
        self.config = get_config()
        self.secret_key = self.config.clerk_secret_key
        self.base_url = "https://api.clerk.com/v1"

    async def create_organization_invitation(
        self,
        org_id: str,
        email: str,
        role: str = "org:member",
        inviter_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an organization invitation via Clerk API.

        Args:
            org_id: Clerk organization ID
            email: Email address to invite
            role: Member role ('org:admin' or 'org:member')
            inviter_user_id: Optional user ID of person sending invite

        Returns:
            Invitation data from Clerk API

        Raises:
            httpx.HTTPStatusError: If API request fails (rate limit, invalid email, etc.)
        """
        url = f"{self.base_url}/organizations/{org_id}/invitations"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "email_address": email,
            "role": role
        }
        if inviter_user_id:
            payload["inviter_user_id"] = inviter_user_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def list_organization_invitations(
        self,
        org_id: str,
        status: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List organization invitations from Clerk API.

        Args:
            org_id: Clerk organization ID
            status: Filter by status (e.g., ['pending', 'accepted', 'revoked', 'expired'])

        Returns:
            List of invitation data
        """
        url = f"{self.base_url}/organizations/{org_id}/invitations"
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        params = {}
        if status:
            params["status"] = ",".join(status)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            # Clerk returns paginated response: {data: [...], total_count: N}
            return data.get("data", [])

    async def revoke_organization_invitation(
        self,
        org_id: str,
        invitation_id: str,
        requesting_user_id: str
    ) -> Dict[str, Any]:
        """
        Revoke (cancel) an organization invitation via Clerk API.

        Args:
            org_id: Clerk organization ID
            invitation_id: Invitation ID to revoke
            requesting_user_id: User ID performing the revocation

        Returns:
            Revoked invitation data
        """
        url = f"{self.base_url}/organizations/{org_id}/invitations/{invitation_id}/revoke"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "requesting_user_id": requesting_user_id
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def remove_organization_member(
        self,
        org_id: str,
        user_id: str
    ) -> bool:
        """
        Remove a member from an organization via Clerk API.

        Args:
            org_id: Clerk organization ID
            user_id: User ID to remove

        Returns:
            True if removed successfully

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.base_url}/organizations/{org_id}/memberships/{user_id}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            return True

    async def update_organization_member_role(
        self,
        org_id: str,
        user_id: str,
        role: str
    ) -> Dict[str, Any]:
        """
        Update a member's role in an organization via Clerk API.

        Args:
            org_id: Clerk organization ID
            user_id: User ID to update
            role: New role ('org:admin' or 'org:member')

        Returns:
            Updated membership data

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.base_url}/organizations/{org_id}/memberships/{user_id}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        payload = {"role": role}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def delete_organization(
        self,
        org_id: str
    ) -> bool:
        """
        Delete an organization via Clerk API.

        Args:
            org_id: Clerk organization ID

        Returns:
            True if deleted successfully

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.base_url}/organizations/{org_id}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            return True

    async def get_organization_members(
        self,
        org_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all members of an organization from Clerk API.

        Args:
            org_id: Clerk organization ID

        Returns:
            List of membership data with user info

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.base_url}/organizations/{org_id}/memberships"
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def get_organization(
        self,
        org_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get organization details from Clerk API.

        Args:
            org_id: Clerk organization ID

        Returns:
            Organization data dict or None if not found

        Raises:
            httpx.HTTPStatusError: If API request fails (except 404)
        """
        url = f"{self.base_url}/organizations/{org_id}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

    async def create_organization(
        self,
        name: str,
        slug: str,
        created_by: str,
        public_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create an organization via Clerk API.

        Args:
            name: Organization name
            slug: URL-safe unique identifier
            created_by: User ID of the creator
            public_metadata: Optional metadata (e.g., industry)

        Returns:
            Created organization data from Clerk

        Raises:
            httpx.HTTPStatusError: If API request fails (422 for duplicate slug, etc.)
        """
        url = f"{self.base_url}/organizations"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "name": name,
            "slug": slug,
            "created_by": created_by,
        }
        if public_metadata:
            payload["public_metadata"] = public_metadata

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()


# Global singleton
_clerk_client = None


def get_clerk_client() -> ClerkClient:
    """Get or create the global Clerk client instance."""
    global _clerk_client
    if _clerk_client is None:
        _clerk_client = ClerkClient()
    return _clerk_client
