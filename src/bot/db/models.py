from datetime import datetime, timedelta

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from bot.db.base import Base


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
            "id": self.file_id,
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

    sanitary_last = Column(Boolean, default=False)
    penis_size = Column(Integer, default=0, index=True)
    last_penis_update = Column(
        DateTime, default=datetime.utcnow() - timedelta(hours=12)
    )

    def __init__(self, chat_id: int, user_id: int):
        self.chat_id = chat_id
        self.user_id = user_id

    def __repr__(self):
        return f"<User {self.id}>"
