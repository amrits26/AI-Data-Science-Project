-- Database indexes for Imperial Cars production workloads

CREATE INDEX IF NOT EXISTS idx_cars_make_model ON cars(make, model);
CREATE INDEX IF NOT EXISTS idx_cars_year ON cars(year);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);
CREATE INDEX IF NOT EXISTS idx_service_jobs_status ON service_jobs(status);
CREATE INDEX IF NOT EXISTS idx_service_jobs_salesperson_id ON service_jobs(salesperson_id);
CREATE INDEX IF NOT EXISTS idx_service_jobs_customer_status ON service_jobs(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_nurture_log_customer_sent_at ON nurture_log(customer_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_market_prices_car_date ON market_prices(car_id, date);
CREATE INDEX IF NOT EXISTS idx_lead_contacts_customer_contacted_at ON lead_contacts(customer_id, contacted_at);
CREATE INDEX IF NOT EXISTS idx_lead_contacts_contact_type ON lead_contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_daily_goals_salesperson_date ON daily_goals(salesperson_id, goal_date);
CREATE INDEX IF NOT EXISTS idx_triage_sessions_session_id ON triage_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_triage_sessions_customer_id ON triage_sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_followup_log_salesperson_id ON followup_log(salesperson_id);
CREATE INDEX IF NOT EXISTS idx_service_videos_customer_id ON service_videos(customer_id);
CREATE INDEX IF NOT EXISTS idx_service_videos_access_token ON service_videos(access_token);
