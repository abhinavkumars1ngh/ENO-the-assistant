import uuid

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True) # Used for admin
    email = Column(String, unique=True, index=True, nullable=True) # Used for Google OAuth
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="user") # 'admin' or 'user'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Account / tier info (device independent). 'free' | 'plus' | 'pro'
    plan = Column(String, default="free", nullable=False, server_default="free")
    plan_updated_at = Column(DateTime(timezone=True), nullable=True)
    # Stable, opaque, non-guessable ID. The browser uses it to namespace the
    # on-device chat vault, so two accounts on one browser never share data and
    # a reset DB can never re-issue an ID that points at someone else's vault.
    public_id = Column(String, unique=True, index=True, nullable=True, default=lambda: uuid.uuid4().hex)

    # Relationship to conversations
    # NOTE: Chats now live on the user's device (IndexedDB). The conversations/messages
    # tables below are legacy and are no longer written to.
    conversations = relationship("Conversation", back_populates="user")


class UsageEvent(Base):
    """Usage METADATA only (who/when/which model/how much). Never message bodies."""
    __tablename__ = "usage_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    kind = Column(String, default="chat")  # chat | transcribe
    model = Column(String, nullable=True)
    output_chars = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)

    __table_args__ = (Index("ix_usage_user_created", "user_id", "created_at"),)


class Payment(Base):
    """One row per Razorpay order. Used to verify checkout belongs to the right user and plan."""
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan = Column(String, nullable=False)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String, default="INR")
    razorpay_order_id = Column(String, unique=True, index=True, nullable=False)
    razorpay_payment_id = Column(String, nullable=True)
    status = Column(String, default="created")  # created | paid | failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Nullable temporarily for migration
    title = Column(String)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    course = Column(String)
    mode = Column(String)
    summary = Column(Text)
    
    user = relationship("User", back_populates="conversations")
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


class HostEndpoint(Base):
    """
    Registry of host machine endpoints for companion-device and org discovery.
    owner_type: 'user' or 'org'
    owner_id: user.id (if owner_type=='user') or org_id (if owner_type=='org')
    """
    __tablename__ = "host_endpoints"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, index=True, nullable=False)
    owner_type = Column(String, default="user", nullable=False) # 'user' | 'org'
    endpoint_url = Column(String, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_host_endpoints_owner", "owner_type", "owner_id"),)


class OrgMember(Base):
    """Stub table for future organization-level access and endpoint sharing."""
    __tablename__ = "org_members"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String, default="member", nullable=False) # 'owner' | 'admin' | 'member'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_org_user", "org_id", "user_id"),)
