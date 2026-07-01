from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    main_url = Column(String, index=True)
    name = Column(String, default="Análisis sin nombre")
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    total_urls = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    total_warnings = Column(Integer, default=0)
    total_notices = Column(Integer, default=0)
    global_summary = Column(Text, nullable=True)
    max_pages = Column(Integer, default=10)
    wp_fingerprint = Column(JSON, nullable=True)

    reports = relationship("PageReport", back_populates="analysis", cascade="all, delete-orphan")

class PageReport(Base):
    __tablename__ = "page_reports"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"))
    url = Column(String)
    status = Column(String, default="ok")  # ok | error
    error_msg = Column(Text, nullable=True)
    issues = Column(JSON, default=list)
    errors_count = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)
    notices_count = Column(Integer, default=0)
    page_title = Column(String, nullable=True)

    analysis = relationship("Analysis", back_populates="reports")
