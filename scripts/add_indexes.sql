-- Imperial Cars AI - Database Indexes
-- Improves query performance on frequently filtered/joined columns
-- Run after init_db.py

-- Customer lookups
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_telegram_id ON customers(telegram_id);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

-- Vehicle searches
CREATE INDEX IF NOT EXISTS idx_cars_make ON cars(make);
CREATE INDEX IF NOT EXISTS idx_cars_model ON cars(model);
CREATE INDEX IF NOT EXISTS idx_cars_year ON cars(year);
CREATE INDEX IF NOT EXISTS idx_cars_make_model_year ON cars(make, model, year);

-- Service job queries
CREATE INDEX IF NOT EXISTS idx_service_jobs_customer_id ON service_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_service_jobs_salesperson_id ON service_jobs(salesperson_id);
CREATE INDEX IF NOT EXISTS idx_service_jobs_vehicle_id ON service_jobs(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_service_jobs_status ON service_jobs(status);
CREATE INDEX IF NOT EXISTS idx_service_jobs_due_date ON service_jobs(due_date);

-- Vehicle lookups
CREATE INDEX IF NOT EXISTS idx_vehicles_customer_id ON vehicles(customer_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles(vin);

-- Service event queries
CREATE INDEX IF NOT EXISTS idx_service_events_vehicle_id ON service_events(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_service_events_service_date ON service_events(service_date);

-- Nurture log queries
CREATE INDEX IF NOT EXISTS idx_nurture_log_customer_id ON nurture_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_nurture_log_message_type ON nurture_log(message_type);
CREATE INDEX IF NOT EXISTS idx_nurture_log_sent_at ON nurture_log(sent_at);

-- Followup log queries (new)
CREATE INDEX IF NOT EXISTS idx_followup_log_customer_id ON followup_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_followup_log_salesperson_id ON followup_log(salesperson_id);
CREATE INDEX IF NOT EXISTS idx_followup_log_channel ON followup_log(channel);
CREATE INDEX IF NOT EXISTS idx_followup_log_status ON followup_log(status);
CREATE INDEX IF NOT EXISTS idx_followup_log_timestamp ON followup_log(timestamp);

-- Market price lookups
CREATE INDEX IF NOT EXISTS idx_market_prices_car_id ON market_prices(car_id);
CREATE INDEX IF NOT EXISTS idx_market_prices_date ON market_prices(date);

-- Carfax record lookups
CREATE INDEX IF NOT EXISTS idx_carfax_records_vin ON carfax_records(vin);

-- Job updates
CREATE INDEX IF NOT EXISTS idx_job_updates_job_id ON job_updates(job_id);
CREATE INDEX IF NOT EXISTS idx_job_updates_created_at ON job_updates(created_at);

-- Lead contact workflow
CREATE INDEX IF NOT EXISTS idx_lead_contacts_customer_id ON lead_contacts(customer_id);
CREATE INDEX IF NOT EXISTS idx_lead_contacts_contact_type ON lead_contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_lead_contacts_outcome ON lead_contacts(outcome);
CREATE INDEX IF NOT EXISTS idx_lead_contacts_contacted_at ON lead_contacts(contacted_at);

-- Daily goals
CREATE INDEX IF NOT EXISTS idx_daily_goals_salesperson_date ON daily_goals(salesperson_id, goal_date);

-- Phase 4 triage session tracking
CREATE INDEX IF NOT EXISTS idx_triage_sessions_session_id ON triage_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_triage_sessions_customer_id ON triage_sessions(customer_id);

-- Service video walkarounds
CREATE INDEX IF NOT EXISTS idx_service_videos_customer_id ON service_videos(customer_id);
CREATE INDEX IF NOT EXISTS idx_service_videos_salesperson_id ON service_videos(salesperson_id);
CREATE INDEX IF NOT EXISTS idx_service_videos_access_token ON service_videos(access_token);
CREATE INDEX IF NOT EXISTS idx_service_videos_approval_status ON service_videos(approval_status);
