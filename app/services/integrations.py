from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IntegrationType
from app.models.integration import Integration
from app.models.user import User


class IntegrationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_type(self, user: User, integration_type: IntegrationType) -> Integration | None:
        return await self.session.scalar(
            select(Integration).where(
                Integration.user_id == user.id,
                Integration.integration_type == integration_type,
            )
        )

    async def disconnect(self, user: User, integration_type: IntegrationType) -> bool:
        integration = await self.get_by_type(user=user, integration_type=integration_type)
        if integration is None:
            return False

        await self.session.delete(integration)
        await self.session.flush()
        return True

    async def upsert_oauth_tokens(
        self,
        user: User,
        integration_type: IntegrationType,
        access_token: str,
        refresh_token: str | None,
        scopes: str | None,
        external_account_id: str | None,
        external_account_name: str | None,
        expires_in: int | None,
    ) -> Integration:
        integration = await self.get_by_type(user=user, integration_type=integration_type)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None

        if integration is None:
            integration = Integration(
                user_id=user.id,
                integration_type=integration_type,
            )
            self.session.add(integration)

        integration.access_token = access_token
        integration.refresh_token = refresh_token
        integration.scopes = scopes
        integration.external_account_id = external_account_id
        integration.external_account_name = external_account_name
        integration.expires_at = expires_at
        await self.session.flush()
        return integration
