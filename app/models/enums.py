from enum import StrEnum


class IntegrationType(StrEnum):
    poe_oauth = "poe_oauth"
    poe_trade = "poe_trade"
    poe_ninja = "poe_ninja"
    funpay = "funpay"


class NotificationType(StrEnum):
    sale = "sale"
    price_alert = "price_alert"
    system = "system"


class SubscriptionType(StrEnum):
    free = "free"
    pro = "pro"
