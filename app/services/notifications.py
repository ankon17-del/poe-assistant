from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.user import User


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, user: User, notification_type: NotificationType, message: str) -> Notification:
        notification = Notification(user_id=user.id, notification_type=notification_type, message=message)
        self.session.add(notification)
        await self.session.flush()
        return notification

