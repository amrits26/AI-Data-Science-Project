# Tablet Test Checklist (Imperial Cars AI)

Date: ____________________
Tester: __________________
Tablet: _________________
URL tested: _____________

Mark each item Pass/Fail and add notes.

## A) Access and load
- [ ] Dashboard opens on tablet URL.
- [ ] No major layout break on tablet portrait mode.
- [ ] No major layout break on tablet landscape mode.

## B) Inventory cards
- [ ] Inventory cards load vehicle images.
- [ ] Year/Make/Model appears correctly.
- [ ] Price/spec fields render (MPG/HP/etc if available).
- [ ] Ask AI action opens chat flow.

## C) Chatbot sample questions
Ask and verify response quality:
- [ ] "What is towing capacity of Silverado 1500?"
- [ ] "Compare RAV4 vs CR-V for family use."
- [ ] "How does financing work with low down payment?"
- [ ] "What are pros/cons of buying used vs new?"
- [ ] "Which SUV under $35k has best reliability?"

## D) Payment estimator
- [ ] Enter sample: price 25000, down 5000, APR 5.0, term 60.
- [ ] Monthly payment updates correctly.
- [ ] Savings/summary panel updates.

## E) Trade-in wizard
- [ ] Step 1 (vehicle details) works.
- [ ] Step 2 (condition/mileage) works.
- [ ] Estimate is returned.
- [ ] Save/resume flow works.

## F) Paperwork OCR upload
- [ ] Upload sample lead sheet image.
- [ ] OCR extracts key fields.
- [ ] No server error on submission.

## G) Mode controls
- [ ] Customer mode tabs show expected customer tools.
- [ ] Salesperson mode prompts for PIN.
- [ ] Salesperson mode unlocks with valid PIN.

## H) API/system checks
- [ ] /api/health returns ok/degraded with expected details.
- [ ] Ollama is reachable from backend.

## Overall result
- [ ] GO for demo
- [ ] NO-GO (fixes required)

Notes / blockers:

1. __________________________________________
2. __________________________________________
3. __________________________________________
