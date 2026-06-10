


"""
SQLAlchemy ORM Models for Imperial Cars PostgreSQL Database

Tables:
- cars: Vehicle master data (make, model, year, specs, pricing, ratings)
- market_prices: Historical pricing trends
- carfax_records: Vehicle history (accidents, owners, service dates)
- service_jobs: Service appointments and maintenance tracking
- job_updates: Status updates for service jobs
- customers: Customer master data (name, contact, telegram_id)
- vehicles: Customer-owned vehicles
- service_events: Historical service events per vehicle
- nurture_log: Audit log for lifecycle agent messages
"""

from datetime import datetime, timezone
from typing import Optional

from backend.app.core.platform_compat import patch_platform_machine_for_windows

patch_platform_machine_for_windows()

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Date, JSON
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def _utcnow() -> datetime:
    """Return UTC timestamp as naive datetime for DB compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# --- LEAD CAPTURE ---

# --- LEAD CAPTURE ---
class Lead(Base):
    """Captured sales lead from chatbot conversation."""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    preferred_contact_time = Column(String(100), nullable=True)
    vehicle_interest = Column(String(200), nullable=True)
    budget = Column(String(100), nullable=True)
    trade_in = Column(String(200), nullable=True)
    financing_needs = Column(String(200), nullable=True)
    conversation_context = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    followup_sent = Column(Boolean, default=False, index=True)

    def __repr__(self):
        return f"<Lead name={self.name} phone={self.phone} vehicle={self.vehicle_interest}>"


# --- FOLLOWUP TRACKING ---
class Followup(Base):
    """Tracks follow-up messages sent to leads."""
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    channel = Column(String(32), default="chat", nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)


class Car(Base):
    """Master vehicle catalog."""
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    make = Column(String(100), index=True)
    model = Column(String(100), index=True)
    year = Column(Integer, index=True)
    trim = Column(String(100), nullable=True)
    vin = Column(String(32), index=True, nullable=True)
    stock_number = Column(String(64), index=True, nullable=True)
    detail_url = Column(String(500), nullable=True)
    carfax_url = Column(String(500), nullable=True)  # Scraped Carfax link
    color = Column(String(50), nullable=True)
    mileage = Column(Integer, nullable=True)
    available = Column(Boolean, default=True, index=True)
    availability_status = Column(String(20), default="available", index=True)  # available | sold | pending
    last_seen = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=_utcnow, index=True)
    engine = Column(String(100), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    horsepower = Column(Integer, nullable=True)
    torque = Column(Integer, nullable=True)
    mpg_city = Column(Float, nullable=True)
    mpg_highway = Column(Float, nullable=True)
    transmission = Column(String(50), nullable=True)
    drivetrain = Column(String(50), nullable=True)
    msrp = Column(Float, nullable=True)
    invoice_price = Column(Float, nullable=True)
    used_avg_price = Column(Float, nullable=True)
    reliability_score = Column(Float, nullable=True)  # 1-100 scale
    safety_rating = Column(Float, nullable=True)  # NHTSA overall rating
    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    curb_weight = Column(Integer, nullable=True)
    towing_capacity = Column(Integer, nullable=True)
    fuel_tank_capacity = Column(Float, nullable=True)
    spec_source = Column(String(100), nullable=True)
    warranty_years = Column(Integer, nullable=True)
    common_issues = Column(Text, nullable=True)  # JSON or comma-separated
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    market_prices = relationship("MarketPrice", back_populates="car", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Car {self.year} {self.make} {self.model}>"


class MarketPrice(Base):
    """Historical market pricing for cars."""
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id", ondelete="CASCADE"), index=True)
    date = Column(Date, index=True, default=lambda: _utcnow().date())
    price = Column(Float, nullable=False)
    source = Column(String(100), nullable=True)  # "initial_import", "nada", "kbb", "market_snapshot"
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    car = relationship("Car", back_populates="market_prices")

    def __repr__(self):
        return f"<MarketPrice car_id={self.car_id} price={self.price}>"


class CarfaxRecord(Base):
    """Vehicle history from Carfax or NHTSA VIN lookup."""
    __tablename__ = "carfax_records"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), unique=True, index=True)
    year = Column(Integer, nullable=True)
    make = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    accident_count = Column(Integer, default=0)
    owner_count = Column(Integer, default=0)
    last_service_date = Column(Date, nullable=True)
    odometer_miles = Column(Integer, nullable=True)
    title_status = Column(String(50), nullable=True)  # "Clean", "Salvage", "Lemon", etc.
    raw_data = Column(JSON, nullable=True)  # Full NHTSA or Carfax JSON response
    source = Column(String(100), nullable=True)  # "nhtsa", "carfax_pdf", "manual_import"
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<CarfaxRecord vin={self.vin}>"


class Customer(Base):
    """Customer master data."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True, index=True)
    telegram_id = Column(Integer, nullable=True, unique=True, index=True)
    preferred_contact = Column(String(50), nullable=True)  # "email", "phone", "telegram", "sms"
    preferred_channels = Column(JSON, nullable=True)  # e.g. ["sms", "whatsapp", "email", "voice"]
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_purchase_date = Column(Date, nullable=True)
    sale_price_last = Column(Float, nullable=True)

    # Relationships
    vehicles = relationship("Vehicle", back_populates="customer", cascade="all, delete-orphan")
    service_jobs = relationship(
        "ServiceJob",
        back_populates="customer",
        cascade="all, delete-orphan",
        foreign_keys="ServiceJob.customer_id",
    )
    lead_contacts = relationship(
        "LeadContact",
        back_populates="customer",
        cascade="all, delete-orphan",
        foreign_keys="LeadContact.customer_id",
    )
    nurture_logs = relationship("NurtureLog", back_populates="customer", cascade="all, delete-orphan")
    channel_prefs = relationship("CustomerChannelPref", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.name}>"


class Vehicle(Base):
    """Customer-owned vehicles."""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    vin = Column(String(17), nullable=True, index=True)
    year = Column(Integer, nullable=True)
    make = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)
    color = Column(String(50), nullable=True)
    purchase_date = Column(Date, nullable=True)
    mileage = Column(Integer, nullable=True)
    condition = Column(String(50), nullable=True)  # "excellent", "good", "fair", "poor"
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="vehicles")
    service_events = relationship("ServiceEvent", back_populates="vehicle", cascade="all, delete-orphan")
    service_jobs = relationship("ServiceJob", back_populates="vehicle", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vehicle {self.year} {self.make} {self.model} (customer_id={self.customer_id})>"


class ServiceJob(Base):
    """Service appointments and maintenance tracking."""
    __tablename__ = "service_jobs"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    salesperson_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String(100), index=True)  # "oil_change", "tire_rotation", "inspection", etc.
    status = Column(String(50), default="pending", index=True)  # "pending", "in_progress", "completed", "cancelled"
    priority = Column(String(50), nullable=True)  # "low", "medium", "high", "urgent"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    due_date = Column(Date, nullable=True, index=True)
    completed_date = Column(Date, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="service_jobs", foreign_keys=[customer_id])
    salesperson = relationship("Customer", foreign_keys=[salesperson_id])
    vehicle = relationship("Vehicle", back_populates="service_jobs")
    updates = relationship("JobUpdate", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ServiceJob {self.job_type} (customer_id={self.customer_id}, status={self.status})>"


class JobUpdate(Base):
    """Status updates for service jobs."""
    __tablename__ = "job_updates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("service_jobs.id", ondelete="CASCADE"), index=True)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    # Relationships
    job = relationship("ServiceJob", back_populates="updates")

    def __repr__(self):
        return f"<JobUpdate job_id={self.job_id} status={self.status}>"


class ServiceEvent(Base):
    """Historical service events per vehicle."""
    __tablename__ = "service_events"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    event_type = Column(String(100), index=True)  # "maintenance", "repair", "recall", "inspection"
    service_date = Column(Date, index=True)
    mileage_at_service = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="service_events")

    def __repr__(self):
        return f"<ServiceEvent {self.event_type} (vehicle_id={self.vehicle_id})>"


class NurtureLog(Base):
    """Audit log for lifecycle agent messages (nurture, prospect, sales)."""
    __tablename__ = "nurture_log"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    message_type = Column(String(100), index=True)  # "milestone_30d", "milestone_90d", "prospect_reengagement", "sales_followup"
    message_body = Column(Text, nullable=True)
    channel = Column(String(50), nullable=True)  # "telegram", "email", "sms"
    days_after_sale = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=_utcnow, index=True)
    delivery_status = Column(String(50), nullable=True)  # "sent", "failed", "pending"
    response = Column(Text, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="nurture_logs")

    def __repr__(self):
        return f"<NurtureLog customer_id={self.customer_id} type={self.message_type}>"


class FollowupLog(Base):
    """Audit log for unified follow-up attempts (SMS, voice, email via Twilio)."""
    __tablename__ = "followup_log"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    salesperson_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), index=True)  # "sms", "voice", "email"
    status = Column(String(50), index=True)  # "sent", "failed", "pending"
    message_body = Column(Text, nullable=True)
    recipient = Column(String(255), nullable=True)  # phone or email
    timestamp = Column(DateTime, default=_utcnow, index=True)
    response = Column(JSON, nullable=True)  # Full Twilio API response
    error = Column(Text, nullable=True)

    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])

    def __repr__(self):
        return f"<FollowupLog customer_id={self.customer_id} channel={self.channel} status={self.status}>"


class CustomerChannelPref(Base):
    """Per-customer outbound communication preferences."""
    __tablename__ = "customer_channel_prefs"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    channel = Column(String(50), index=True)  # "sms", "whatsapp", "email", "voice"
    is_enabled = Column(Boolean, default=True, nullable=False)
    contact_value = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    customer = relationship("Customer", back_populates="channel_prefs")

    def __repr__(self):
        return f"<CustomerChannelPref customer_id={self.customer_id} channel={self.channel} enabled={self.is_enabled}>"


class LeadContact(Base):
    """Track each outbound/inbound lead contact attempt and outcome."""
    __tablename__ = "lead_contacts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False)
    salesperson_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_type = Column(String(50), index=True, nullable=False)  # call/email/text/voicemail/in-person
    notes = Column(Text, nullable=True)
    outcome = Column(String(100), nullable=True, index=True)
    contacted_at = Column(DateTime, default=_utcnow, index=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)

    customer = relationship("Customer", back_populates="lead_contacts", foreign_keys=[customer_id])
    salesperson = relationship("Customer", foreign_keys=[salesperson_id])

    def __repr__(self):
        return f"<LeadContact customer_id={self.customer_id} contact_type={self.contact_type} outcome={self.outcome}>"


class DailyGoal(Base):
    """Per-salesperson daily outreach targets."""
    __tablename__ = "daily_goals"

    id = Column(Integer, primary_key=True, index=True)
    salesperson_id = Column(String(100), index=True, nullable=False)
    goal_date = Column(Date, index=True, nullable=False)
    call_goal = Column(Integer, default=0, nullable=False)
    text_goal = Column(Integer, default=0, nullable=False)
    email_goal = Column(Integer, default=0, nullable=False)
    appointment_goal = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<DailyGoal salesperson_id={self.salesperson_id} date={self.goal_date}>"


class TriageSession(Base):
    """Stores first-interaction triage answers used for recommendation matching."""
    __tablename__ = "triage_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    answers = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)

    customer = relationship("Customer")

    def __repr__(self):
        return f"<TriageSession session_id={self.session_id} customer_id={self.customer_id}>"


class SessionSnapshot(Base):
    """Stores lightweight snapshots for resumable customer journeys."""
    __tablename__ = "session_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)

    customer = relationship("Customer")

    def __repr__(self):
        return f"<SessionSnapshot session_id={self.session_id} customer_id={self.customer_id}>"


class ServiceVideo(Base):
    """Service walkaround video uploads with signed access and approval status."""
    __tablename__ = "service_videos"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    salesperson_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=True)
    access_token = Column(String(120), index=True, nullable=False)
    token_expires_at = Column(DateTime, nullable=True, index=True)
    approval_status = Column(String(30), default="pending", index=True)
    approved_at = Column(DateTime, nullable=True)
    approval_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    customer = relationship("Customer", foreign_keys=[customer_id])
    salesperson = relationship("Customer", foreign_keys=[salesperson_id])

    def __repr__(self):
        return f"<ServiceVideo id={self.id} customer_id={self.customer_id} status={self.approval_status}>"


class ResumeDealSession(Base):
    """Stores resumable deal sessions sent to customers via SMS/email links."""
    __tablename__ = "resume_deal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(30), nullable=True, index=True)
    payment_estimate = Column(Float, nullable=True)
    trade_in_estimate = Column(Float, nullable=True)
    snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    resumed_at = Column(DateTime, nullable=True, index=True)

    customer = relationship("Customer")
    car = relationship("Car")

    def __repr__(self):
        return f"<ResumeDealSession token={self.token} customer_id={self.customer_id}>"


class SalesStageEvent(Base):
    """Audit trail for dealership sales stage transitions."""
    __tablename__ = "sales_stage_events"

    id = Column(Integer, primary_key=True, index=True)
    stock_number = Column(String(100), index=True, nullable=False)
    stage = Column(String(100), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    salesperson_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    customer = relationship("Customer", foreign_keys=[customer_id])
    salesperson = relationship("Customer", foreign_keys=[salesperson_id])

    def __repr__(self):
        return f"<SalesStageEvent stock_number={self.stock_number} stage={self.stage}>"

