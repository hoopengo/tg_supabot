from sqlalchemy import Column, Integer, String

from bot.db.base import Base


class MessageModel(Base):
    __tablename__ = "message"

    id = Column(Integer, unique=True, primary_key=True, index=True, nullable=False)
    file_id = Column(String, unique=True, nullable=False)
    set_name = Column(String, nullable=False)

    def __init__(self, message_id: int, file_id: str, set_name: str):
        self.id = message_id
        self.file_id = file_id
        self.set_name = set_name

    def __repr__(self):
        return f"<Message {self.id}>"
