from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, index=True) # UUID
    title = Column(String, index=True)
    course = Column(String, index=True)
    type = Column(String) # pdf, slide, etc
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    hash = Column(String, index=True)
    pages = Column(Integer)
    author = Column(String)
    source = Column(String)
    status = Column(String) # processing, ready, failed
    filepath = Column(String)

class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True, index=True) # UUID or YouTube ID
    title = Column(String, index=True)
    channel = Column(String)
    duration = Column(Integer)
    transcript_path = Column(String)
    summary = Column(Text)
    status = Column(String)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, index=True) # UUID
    title = Column(String)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    course = Column(String)
    mode = Column(String)
    summary = Column(Text)
    
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String) # user, assistant
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    references = Column(JSON) # Storing retrieved chunks metadata
    
    conversation = relationship("Conversation", back_populates="messages")

class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String) # working, session, long-term
    fact = Column(Text)
    confidence = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class StudyProgress(Base):
    __tablename__ = "study_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String, index=True)
    mastery_percentage = Column(Float)
    weak_topics = Column(JSON)
