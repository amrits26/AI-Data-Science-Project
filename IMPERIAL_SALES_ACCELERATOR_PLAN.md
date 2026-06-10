# Plan: Imperial Cars Sales Accelerator (Phases 0-6)

TL;DR: 130-hour, 7-phase enhancement plan to transform the existing Imperial AI system into a full sales acceleration platform. Builds from accessibility foundations -> dual-mode UI -> psychology-driven sales tools -> Verde automation -> trust features -> portfolio dashboard -> production deployment. Each phase is independently verifiable before the next begins.

## Phase 0 - Accessibility & Content Foundation
**14 hrs** - Must complete first; everything else builds on WCAG-compliant components.

| # | Task | Hrs |
|---|---|---|
| 0.1 | Audit all color pairs for 4.5:1 WCAG contrast; fix any Imperial red/black combos that fail | 2 |
| 0.2 | Add aria-label, role, and alt attributes to all interactive elements and images in src | 3 |
| 0.3 | Keyboard navigation pass - all buttons, modals, and dropdowns reachable via Tab/Enter/Escape | 2 |
| 0.4 | GET /api/buyers-guide/pdf FastAPI endpoint - reportlab-generated PDF of top inventory + FAQs + financing overview | 4 |
| 0.5 | Maintenance Scheduler chat intent in imperial_chatbot.py - plain-language to service interval table; voice-trigger phrase support | 2 |
| 0.6 | tests/test_accessibility.py - contrast, aria, and keyboard focus smoke tests | 1 |

Verify: Lighthouse Accessibility >= 90; keyboard-only tab through full app; /api/buyers-guide/pdf returns valid PDF; chat responds to "when should I change my oil".

## Phase 1 - Dual-Mode UI (Tablet / Mobile)
**22 hrs** - Depends on Phase 0 component baseline.

| # | Task | Hrs |
|---|---|---|
| 1.1 | Add mode context (customer/salesperson) to React state; persist in localStorage | 1 |
| 1.2 | Customer Mode tab bar: Chat, Inventory, Payment Estimator, Schedule Test Drive - hide all admin tabs | 2 |
| 1.3 | Salesperson Mode PIN entry (hash stored in .env as SALESPERSON_PIN_HASH); reveals: Paperwork, Follow-up Logs, Lifecycle Agents, Activity Dashboard | 3 |
| 1.4 | FloatingChatBubble - bottom-right persistent bubble to slide-up drawer with message history + quick-reply chips (Finance, Trade-In, Test Drive, Compare) | 4 |
| 1.5 | Redesigned InventoryCard - hero image, price (bold #B22234), year/make/model/miles, Ask AI button, StockBadge (Only 3 left when qty <= 5) | 4 |
| 1.6 | GET /api/inventory/public - paginated vehicles with scarcity count from cars table | 2 |
| 1.7 | Mobile-first responsive pass (320px-768px portrait + landscape) | 3 |
| 1.8 | Quick-reply chips wire into imperial_chatbot.py as prefilled prompts | 2 |
| 1.9 | TailwindCSS animate-pulse loading skeletons for inventory cards and chat | 1 |

Verify: Customer Mode shows exactly 4 tabs; Salesperson Mode unlocks on correct PIN; bubble persists on every route; InventoryCard renders all fields; 375px mobile renders correctly.

## Phase 2 - Psychology-Driven Sales Tools
**24 hrs** - Parallel with Phase 4 once Phase 1 layout is stable.

| # | Task | Hrs |
|---|---|---|
| 2.1 | Payment Estimator - sliders (price, down, rate, term), anchored MSRP strikethrough, green You save $X bar, orange break-even marker at 48 months | 5 |
| 2.2 | POST /api/finance/estimate - principal + rate + term to monthly payment, total cost, savings vs. MSRP | 2 |
| 2.3 | Progressive Trade-In Wizard (3 steps): year/make/model -> estimate from market_prices; condition+mileage -> revised range; lead capture + Twilio SMS resume link | 6 |
| 2.4 | POST /api/trade-in/estimate - used_avg_price lookup + condition multiplier -> price range | 2 |
| 2.5 | Comparison Radar Chart - 2-3 vehicles on 6 axes (price, MPG, HP, safety, reliability, torque); winner shaded rgba(34,197,94,0.2) with recharts RadarChart | 4 |
| 2.6 | GET /api/social-proof/{car_id} - "X people bought this in 30 days" from followup_log + market_prices; render on InventoryCard | 2 |
| 2.7 | Resume Deal Link - modal captures email/phone; POST /api/resume-deal stores session snapshot and sends Twilio SMS one-tap link | 3 |

Verify: Payment calc correct for $25k/5%/60mo (~$471/mo); trade-in wizard creates customer record; radar chart highlights winner; social proof count increments; resume SMS delivers with correct link.

## Phase 3 - Verde Sales System Automation
**20 hrs** - Can begin parallel with Phase 2.

| # | Task | Hrs |
|---|---|---|
| 3.1 | New lead_contacts table migration: customer_id, contact_type (call/email/text/voicemail/in-person), notes, outcome, contacted_at | 1 |
| 3.2 | POST /api/leads/{id}/contact + GET /api/leads/{id}/contacts - log and retrieve contact attempts | 2 |
| 3.3 | 5-Contacts Progress Bar in Salesperson Mode - per-lead card with 5 icon slots filled on completion | 3 |
| 3.4 | daily_goals table + PUT /api/goals/today - set/update salesperson daily goals | 1 |
| 3.5 | Daily Activity Goal Dashboard - progress rings (CSS conic-gradient), goals vs actuals; confetti animation at 100% | 3 |
| 3.6 | Tie-Down Detector in imperial_chatbot.py - buying-signal regex patterns with tie-down suggestion | 3 |
| 3.7 | POST /api/leads/{id}/score - lead score and Hot/Warm/Cold tiering | 2 |
| 3.8 | Follow-up Cadence Engine in lifecycle_agents.py - tier-based scheduling + followup_log + Twilio reminders | 4 |
| 3.9 | Lead score badge on lead list in Salesperson Mode | 1 |

Verify: Contact log updates progress bar immediately; 100% triggers confetti; tie-down fires on buying-signal phrasing; lead score and cadence timing are correct.

## Phase 4 - Trust & Relationship Features
**18 hrs** - Parallel with Phase 2 once Phase 1 is stable.

| # | Task | Hrs |
|---|---|---|
| 4.1 | Trust Badge - GET /api/stats/customer-count -> Trusted by X Imperial families | 1 |
| 4.2 | Role Detector in imperial_chatbot.py - buyer/researcher/service/finance classification and tone control | 3 |
| 4.3 | Conflict Resolution Mode - price-objection detection with 3 structured chat buttons | 3 |
| 4.4 | Walk Away Button - Save & Exit on payment estimator/chat, resume-deal trigger, followup_log walkaway entry | 2 |
| 4.5 | Service Heart Message in lifecycle_agents.py at 30/90/365 days post-sale; relational copy only | 2 |
| 4.6 | True Need Triage - first-interaction 3-question sequential chat flow | 4 |
| 4.7 | POST /api/triage - store triage answers and return top 3 inventory matches | 2 |
| 4.8 | Unit tests for role detector, conflict detection, triage recommender | 1 |

Verify: Trust badge shows live DB count; role detector classifies test messages; conflict mode fires on objection wording; Walk Away logs and sends resume link; Service Heart timing passes with date mocks; triage returns filtered recommendations.

## Phase 5 - Portfolio & Content Accessibility
**22 hrs** - Depends on Phase 3 and Phase 0.

| # | Task | Hrs |
|---|---|---|
| 5.1 | Add salesperson_id FK to followup_log and service_jobs migration | 1 |
| 5.2 | GET /api/dashboard/me - conversion rate, avg profit, month sold, YTD $100k progress, best-selling brands | 3 |
| 5.3 | Sales Dashboard panel - KPI cards, $100k progress bar, brand chart, Deal of the Day spotlight | 4 |
| 5.4 | Automated Review Request - lifecycle task at 48 hrs post-sale with review links | 3 |
| 5.5 | Service Video Walkaround - upload/store/sign URL/approval webhook flow | 4 |
| 5.6 | GET /api/maintenance-schedule/pdf - reportlab PDF by VIN or make/model/year | 3 |
| 5.7 | Voice Input via window.SpeechRecognition with fallback and aria label | 3 |
| 5.8 | Integration tests: review timing, video flow, voice component | 1 |

Verify: Dashboard math valid; review SMS timing valid with scheduler mock; video upload and playback path valid; maintenance PDF generates; voice input transcribes and submits correctly.

## Phase 6 - Integration & Deployment
**10 hrs** - Final phase; depends on all prior phases.

| # | Task | Hrs |
|---|---|---|
| 6.1 | setup_task_scheduler.ps1 to run import_imperial_inventory.py every Monday at 02:00 | 1 |
| 6.2 | Structured JSON-lines logging with structlog on all new endpoints | 2 |
| 6.3 | GET /api/health with DB, Twilio, PDF, inventory staleness checks | 2 |
| 6.4 | setup_production.ps1 for install/init/build/start/health flow | 3 |
| 6.5 | .env.example updated with all new variables and comments | 0.5 |
| 6.6 | DEPLOYMENT.md runbook entries for Phases 0-5 | 1 |
| 6.7 | End-to-end manual + scripted smoke test for one full customer journey | 0.5 |

Verify: setup_production.ps1 succeeds on clean env; task scheduler entry visible; health endpoint all green; JSON logs emitted; env keys present.

## Effort Summary

| Phase | Description | Hours |
|---|---|---|
| 0 | Accessibility & Content Foundation | 14 |
| 1 | Dual-Mode UI | 22 |
| 2 | Psychology Sales Tools | 24 |
| 3 | Verde Sales Automation | 20 |
| 4 | Trust & Relationship Features | 18 |
| 5 | Portfolio & Content | 22 |
| 6 | Integration & Deployment | 10 |
| Total |  | 130 |

Recommended sprint order: 0 -> 1 -> 3 -> 4 -> 2 -> 5 -> 6.
Phases 2 and 4 can run in parallel once Phase 1 layout is stable.

## Relevant Files
- frontend-react/src/App.tsx
- frontend-react/src/components/
- frontend-react/src/pages/
- backend/app/agents/imperial_chatbot.py
- backend/app/agents/lifecycle_agents.py
- backend/app/main.py
- backend/app/database/models.py
- scripts/import_imperial_inventory.py
- requirements.txt

## Decisions Needed Before Coding
- Salesperson PIN: what hash should be stored in SALESPERSON_PIN_HASH?
- Review links: Google Maps, Cars.com, DealerRater URLs.
- $100k goal: fixed or configurable per salesperson?
- PDF library: reportlab or weasyprint?
- Video storage: local path or S3-compatible bucket?
- Dashboard scope: all salesperson PINs or admin-only?

## Execution Status
- Phase 0 complete and verified.
- Phase 1 currently in progress.
- Task 1.1 completed in code: mode context + localStorage persistence added.
