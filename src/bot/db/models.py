from datetime import datetime, timedelta
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from bot.db.base import Base


class QueueStatus(str, PyEnum):
    OPEN = "open"
    CLOSED = "closed"


class MemberStatus(str, PyEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class SwapStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AdminRole(str, PyEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"


def _enum_values(enums):
    return [e.value for e in enums]


class StickerMessageModel(Base):
    __tablename__ = "sticker_message"

    id = Column(BigInteger, unique=True, primary_key=True, index=True, nullable=False)
    file_id = Column(String, unique=True, nullable=False)
    set_name = Column(String, nullable=False)

    def __init__(self, message_id: int, file_id: str, set_name: str):
        self.id = message_id
        self.file_id = file_id
        self.set_name = set_name

    def as_dict(self) -> dict[str, str]:
        """
        Represent MessageModel as dict

        Args:
            self (MessageModel): The message database object.

        Returns:
            dict[str, str]: A dict containing message_model fields.
        """

        return {
            "id": str(self.id),
            "file_id": self.file_id,
            "set_name": self.set_name,
        }

    def __repr__(self):
        return f"<StickerMessage {self.id}>"


class UserModel(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)

    sanitary_last = Column(Boolean, default=False)
    penis_size = Column(Integer, default=0, index=True)
    last_penis_update = Column(
        DateTime, default=lambda: datetime.utcnow() - timedelta(hours=12)
    )
    toxicity_level = Column(Integer, default=0, nullable=False)
    casino_lucky = Column(Boolean, default=False, nullable=False)

    def __init__(
        self,
        chat_id: int,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ):
        self.chat_id = chat_id
        self.user_id = user_id
        self.username = username
        self.first_name = first_name

    def __repr__(self):
        return f"<User {self.id}>"


class QueueModel(Base):
    __tablename__ = "queues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=True)
    title = Column(String(255), nullable=False)
    status = Column(
        Enum(QueueStatus, values_callable=_enum_values),
        nullable=False,
        default=QueueStatus.OPEN,
    )
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Queue {self.id} '{self.title}'>"


class QueueMemberModel(Base):
    __tablename__ = "queue_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_id = Column(
        Integer, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    position = Column(Integer, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(
        Enum(MemberStatus, values_callable=_enum_values),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )

    __table_args__ = (
        Index("ix_queue_members_queue_position", "queue_id", "position"),
        Index("ix_queue_members_queue_user", "queue_id", "user_id"),
    )

    def __repr__(self):
        return f"<QueueMember queue={self.queue_id} user={self.user_id} pos={self.position}>"


class SwapRequestModel(Base):
    __tablename__ = "swap_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_id = Column(
        Integer, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_user_id = Column(BigInteger, nullable=False)
    to_user_id = Column(BigInteger, nullable=False)
    status = Column(
        Enum(SwapStatus, values_callable=_enum_values),
        nullable=False,
        default=SwapStatus.PENDING,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<SwapRequest {self.id} queue={self.queue_id} {self.from_user_id}<->{self.to_user_id}>"


class QueueGroupModel(Base):
    __tablename__ = "queue_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=True)
    title = Column(String(500), nullable=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<QueueGroup {self.id} chat={self.chat_id}>"


class QueueGroupMemberModel(Base):
    __tablename__ = "queue_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(
        Integer,
        ForeignKey("queue_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    queue_id = Column(
        Integer,
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_queue_group_members_group_queue", "group_id", "queue_id", unique=True),
    )

    def __repr__(self):
        return f"<QueueGroupMember group={self.group_id} queue={self.queue_id}>"


class ChatAdminModel(Base):
    __tablename__ = "chat_admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False)
    first_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    role = Column(
        Enum(AdminRole, values_callable=_enum_values),
        nullable=False,
        default=AdminRole.ADMIN,
    )
    added_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_chat_admins_chat_user", "chat_id", "user_id"),)

    def __repr__(self):
        return f"<ChatAdmin chat={self.chat_id} user={self.user_id} role={self.role}>"

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        if self.first_name:
            return self.first_name
        return str(self.user_id)


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    queue_id = Column(Integer, nullable=True)
    actor_user_id = Column(BigInteger, nullable=False)
    action = Column(String(100), nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog {self.id} {self.action}>"


class ChatSettingsModel(Base):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, unique=True, index=True)

    # Command toggles (True = enabled)
    cmd_dick = Column(Boolean, default=True, nullable=False)
    cmd_top_dick = Column(Boolean, default=True, nullable=False)
    cmd_stats = Column(Boolean, default=True, nullable=False)
    cmd_casino = Column(Boolean, default=True, nullable=False)
    cmd_casino_top = Column(Boolean, default=True, nullable=False)
    cmd_slots = Column(Boolean, default=True, nullable=False)
    cmd_sanitary = Column(Boolean, default=True, nullable=False)
    cmd_all = Column(Boolean, default=True, nullable=False)
    cmd_top_toxic = Column(Boolean, default=True, nullable=False)
    cmd_transfer = Column(Boolean, default=True, nullable=False)
    cmd_queues = Column(Boolean, default=True, nullable=False)
    cmd_create_queue = Column(Boolean, default=True, nullable=False)
    cmd_switch = Column(Boolean, default=True, nullable=False)
    cmd_ask = Column(Boolean, default=True, nullable=False)

    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<ChatSettings chat={self.chat_id}>"

    def __init__(self, chat_id: int, **kwargs):
        self.chat_id = chat_id
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Map command name -> column attribute name
    COMMAND_MAP = {
        "dick": "cmd_dick",
        "top_dick": "cmd_top_dick",
        "stats": "cmd_stats",
        "casino": "cmd_casino",
        "casino_top": "cmd_casino_top",
        "slots": "cmd_slots",
        "sanitary": "cmd_sanitary",
        "all": "cmd_all",
        "top_toxic": "cmd_top_toxic",
        "transfer": "cmd_transfer",
        "queues": "cmd_queues",
        "create_queue": "cmd_create_queue",
        "switch": "cmd_switch",
        "ask": "cmd_ask",
    }

    COMMAND_LABELS = {
        "dick": "Писюн (/dick)",
        "top_dick": "Топ размеров (/top_dick)",
        "stats": "Статистика (/stats)",
        "casino": "Казино (/casino)",
        "casino_top": "Топ казино (/casino_top)",
        "slots": "Рулетка (/slots)",
        "sanitary": "Санитарная зона (/sanitary)",
        "all": "Упомянуть всех (/all)",
        "top_toxic": "Топ токсичных (/top_toxic)",
        "transfer": "Перевод (/transfer)",
        "queues": "Очереди (/queues)",
        "create_queue": "Создать очередь (/create_queue)",
        "switch": "Обмен местами (/switch)",
        "ask": "AI ассистент (/ask)",
    }

    def is_command_enabled(self, command: str) -> bool:
        attr = self.COMMAND_MAP.get(command)
        if attr is None:
            return True  # Unknown commands are enabled by default
        return getattr(self, attr, True)
