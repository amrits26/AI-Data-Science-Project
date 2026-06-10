"""Imperial Cars Telegram bot (async, Ollama-only, caption-driven OCR ingestion)."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Any

import httpx
import pandas as pd
import pdfkit
import requests
from jinja2 import Template
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from backend.app.agents.document_ingestion import (
    DOC_TYPES,
    extract_lead_info,
    process_document_image,
    process_lead_image_from_text,
)
from backend.app.agents.dealership_tools import (
    appraise_trade_in,
    daily_briefing,
    detect_damage,
    rank_leads_by_profit,
    score_leads_from_csv,
)
from backend.app.agents.voice_transcribe import transcribe_audio
from backend.app.agents.imperial_chatbot import ask_imperial
from backend.app.agents.math_tools import loan_calculator
from backend.app.agents.nhtsa_api import decode_vin
from backend.app.agents.visualizations import monthly_payment_chart
from backend.app.agents.customer_updates import get_customer_jobs
from backend.app.database import Car, Customer, get_db_session


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _data_dir() -> str:
    path = _env("DATA_DIR", "./data")
    os.makedirs(path, exist_ok=True)
    return path


OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3")


async def _call_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("response", "")).strip() or "No response from Ollama."
    except Exception as exc:
        logger.warning("ollama_call_failed", extra={"error": str(exc)})
        return f"Ollama unavailable. Fallback response: {exc}"


async def on_bot_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global bot error hook for unhandled exceptions."""
    logger.exception("telegram_handler_error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Something went wrong while processing your request. Please try again in a moment."
            )
    except Exception:
        logger.exception("telegram_error_reply_failed")


def _format_lead_item(lead: dict[str, Any]) -> str:
    if "predicted_sale_prob" in lead:
        return (
            f"- {lead.get('customer_name', 'Unknown')} | "
            f"{lead.get('vehicle_interest', '')} | "
            f"prob={lead.get('predicted_sale_prob', 0)} | "
            f"priority={lead.get('priority', 'n/a')}"
        )
    return f"- {lead.get('customer_name', 'Unknown')} | {lead.get('vehicle_interest', '')}"


def _parse_appraise_parts(parts: list[str]) -> tuple[str, str, int, int, str] | None:
    if len(parts) < 4:
        return None
    make = parts[0]

    # Supports both with and without condition.
    if len(parts) >= 5:
        year_s = parts[-3]
        mileage_s = parts[-2]
        condition = parts[-1]
        model = " ".join(parts[1:-3])
    else:
        year_s = parts[-2]
        mileage_s = parts[-1]
        condition = "good"
        model = " ".join(parts[1:-2])

    try:
        year = int(year_s)
        mileage = int(mileage_s)
    except ValueError:
        return None

    if not model:
        return None

    return make, model, year, mileage, condition


async def _run_appraise_reply(update: Update, parts: list[str], image_path: str | None = None) -> None:
    parsed = _parse_appraise_parts(parts)
    if not parsed:
        await update.message.reply_text("Usage: /appraise Toyota Camry 2020 35000 [condition]")
        return

    make, model, year, mileage, condition = parsed
    damage_level = "clean"
    if image_path:
        damage_level = await asyncio.to_thread(detect_damage, image_path)

    appraisal = await asyncio.to_thread(
        appraise_trade_in,
        make,
        model,
        year,
        mileage,
        condition,
        damage_level,
    )
    a = appraisal.get("appraisal", {})
    await update.message.reply_text(
        f"Appraisal {make} {model} {year}:\n"
        f"Recommended: ${a.get('recommended_offer')}\n"
        f"Range: ${a.get('offer_range_low')} - ${a.get('offer_range_high')}\n"
        f"Damage level: {appraisal.get('damage_level', 'clean')}\n"
        f"Damage adjustment: {appraisal.get('damage_adjustment', 1.0)}"
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Imperial Cars AI Assistant is online.\n\n"
        "Send a form photo with caption exactly one of:\n"
        "lead, insurance, cleanup, sold, commission, credit\n\n"
        "Commands:\n"
        "/ask <question>\n"
        "/specs <make model>\n"
        "/compare <car 1> vs <car 2>\n"
        "/price_check <make model>\n"
        "/trade_in_quote\n"
        "/payment_calc\n"
        "/show_chart [price down rate term]\n"
        "/my_jobs\n"
        "/prefs <customer_id> [set <channel> <on|off> [contact]]\n"
        "/followup <customer_id>\n"
        "/schedule_test_drive\n"
        "/briefing\n"
        "/scoreleads\n"
        "/rankleads\n"
        "/appraise Toyota Camry 2020 35000 [condition]\n"
        "/payout STOCK123\n"
        "/help"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Imperial Cars Bot Commands\n\n"
        "/ask <question> - Ask Imperial AI\n"
        "/specs <make model> - Vehicle specs\n"
        "/compare <car 1> vs <car 2> - Compare two models\n"
        "/price_check <make model> - Price snapshot\n"
        "/trade_in_quote - Start VIN/photo trade-in flow\n"
        "/payment_calc - Step-by-step payment calculator\n"
        "/show_chart [price down rate term] - Monthly payment chart\n"
        "/my_jobs - Your service reminders\n"
        "/prefs <customer_id> [set <channel> <on|off> [contact]] - View/update channel preferences\n"
        "/followup <customer_id> - Send preference-based follow-up\n"
        "/schedule_test_drive - Book appointment\n"
        "/briefing, /scoreleads, /rankleads, /appraise, /payout"
    )


def _command_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args:
        return " ".join(context.args).strip()
    text = (update.message.text or "").strip()
    return " ".join(text.split()[1:]).strip() if text.startswith("/") else text


def _find_customer_id_by_telegram(chat_id: int) -> int | None:
    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.telegram_id == chat_id).first()
        return int(customer.id) if customer else None
    except Exception:
        return None
    finally:
        db.close()


def _find_cars(query_text: str, limit: int = 5) -> list[Car]:
    db = get_db_session()
    try:
        q = db.query(Car)
        parts = [p.strip() for p in query_text.split() if p.strip()]
        if parts:
            q = q.filter(Car.make.ilike(f"%{parts[0]}%") | Car.model.ilike(f"%{parts[0]}%"))
        if len(parts) >= 2:
            tail = " ".join(parts[1:])
            q = q.filter(Car.model.ilike(f"%{tail}%") | Car.make.ilike(f"%{tail}%"))
        return q.order_by(Car.year.desc()).limit(limit).all()
    finally:
        db.close()


def _format_specs(car: Car) -> str:
    return (
        f"{car.year} {car.make} {car.model}\n"
        f"MSRP: ${float(car.msrp or 0):,.0f}\n"
        f"Engine: {car.engine or 'N/A'} ({car.horsepower or 'N/A'} hp)\n"
        f"MPG: {car.mpg_city or 'N/A'} city / {car.mpg_highway or 'N/A'} hwy"
    )


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = _command_text(update, context)
    if not question:
        await update.message.reply_text("Usage: /ask What's the price of a Toyota Camry?")
        return

    response = await asyncio.to_thread(ask_imperial, question)
    answer = str(response.get("answer", "No answer available."))
    await update.message.reply_text(answer[:3900])


async def specs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _command_text(update, context)
    if not query:
        await update.message.reply_text("Usage: /specs Toyota Camry")
        return

    cars = await asyncio.to_thread(_find_cars, query, 3)
    if not cars:
        await update.message.reply_text("No matching vehicles found.")
        return

    for car in cars:
        await update.message.reply_text(_format_specs(car))


async def compare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = _command_text(update, context)
    parts = re.split(r"\s+vs\s+", raw, flags=re.IGNORECASE, maxsplit=1)
    if len(parts) != 2:
        await update.message.reply_text("Usage: /compare Toyota Camry vs Honda Accord")
        return

    left, right = parts
    left_cars = await asyncio.to_thread(_find_cars, left.strip(), 1)
    right_cars = await asyncio.to_thread(_find_cars, right.strip(), 1)
    if not left_cars or not right_cars:
        await update.message.reply_text("Could not find one or both vehicles to compare.")
        return

    c1, c2 = left_cars[0], right_cars[0]
    msg = (
        f"Comparison\n\n"
        f"1) {c1.year} {c1.make} {c1.model}\n"
        f"MSRP: ${float(c1.msrp or 0):,.0f}, HP: {c1.horsepower or 'N/A'}, MPG Hwy: {c1.mpg_highway or 'N/A'}\n\n"
        f"2) {c2.year} {c2.make} {c2.model}\n"
        f"MSRP: ${float(c2.msrp or 0):,.0f}, HP: {c2.horsepower or 'N/A'}, MPG Hwy: {c2.mpg_highway or 'N/A'}"
    )
    await update.message.reply_text(msg)


async def price_check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _command_text(update, context)
    if not query:
        await update.message.reply_text("Usage: /price_check Toyota Camry")
        return

    cars = await asyncio.to_thread(_find_cars, query, 10)
    if not cars:
        await update.message.reply_text("No matching vehicles found.")
        return

    lines = ["Pricing:"]
    for car in cars:
        if car.msrp:
            lines.append(f"- {car.year} {car.make} {car.model}: ${float(car.msrp):,.0f}")
    await update.message.reply_text("\n".join(lines[:20]))


async def trade_in_quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_trade_in"] = True
    await update.message.reply_text("Send your VIN (17 chars) or upload a photo of your car.")


async def payment_calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["payment_flow"] = {"step": "price", "data": {}}
    await update.message.reply_text("Enter vehicle price (example: 30000)")


async def show_chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    try:
        price = float(args[0]) if len(args) > 0 else 30000.0
        down = float(args[1]) if len(args) > 1 else 5000.0
        rate = float(args[2]) if len(args) > 2 else 6.9
        term = int(args[3]) if len(args) > 3 else 60
    except Exception:
        await update.message.reply_text("Usage: /show_chart [price down rate term]")
        return

    payload = await asyncio.to_thread(monthly_payment_chart, price, down, rate, term)
    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        await update.message.reply_text("Chart generation failed.")
        return

    await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption="Monthly Payment Chart")


async def my_jobs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    customer_id = await asyncio.to_thread(_find_customer_id_by_telegram, update.message.chat_id)
    if not customer_id:
        await update.message.reply_text("No linked customer profile found for this Telegram account.")
        return

    jobs = await asyncio.to_thread(get_customer_jobs, customer_id)
    if not jobs:
        await update.message.reply_text("No service jobs found.")
        return

    lines = ["Your service jobs:"]
    for job in jobs[:20]:
        lines.append(f"- {job['job_type'].replace('_', ' ').title()} ({job['status']})")
    await update.message.reply_text("\n".join(lines))


async def schedule_test_drive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["test_drive_flow"] = {"step": "date"}
    await update.message.reply_text("When would you like to test drive? (Today, Tomorrow, This Weekend, or YYYY-MM-DD)")


async def briefing_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    briefing = await asyncio.to_thread(daily_briefing)
    lines = [briefing.get("summary", "No briefing available.")]
    for lead in briefing.get("top_leads", [])[:3]:
        lines.append(_format_lead_item(lead))
    await update.message.reply_text("\n".join(lines))


async def scoreleads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scores = await asyncio.to_thread(score_leads_from_csv)
    top = scores.get("top_leads", [])
    if not top:
        await update.message.reply_text(scores.get("message", "No lead scores available yet."))
        return

    lines = [
        f"Leads scored: {scores.get('total_leads', 0)}",
        f"Average sale probability: {scores.get('average_probability', 0)}",
        f"Modeling: {scores.get('modeling_summary', 'N/A')}",
        "Top leads:",
    ]
    for lead in top[:10]:
        lines.append(_format_lead_item(lead))
    await update.message.reply_text("\n".join(lines))


async def rankleads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ranked = await asyncio.to_thread(rank_leads_by_profit)
    if not ranked:
        await update.message.reply_text("No ranking available.")
        return
    if "error" in ranked[0]:
        await update.message.reply_text(ranked[0]["error"])
        return

    lines = ["Top leads by estimated profit:"]
    for row in ranked:
        lines.append(f"- {row.get('customer_name', 'Unknown')}: ${float(row.get('estimated_profit', 0)):.0f}")
    await update.message.reply_text("\n".join(lines))


async def appraise_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    await _run_appraise_reply(update, args)


def _generate_payout_pdf(stock_number: str) -> dict[str, Any]:
    data_dir = _data_dir()
    commission_csv = os.path.join(data_dir, "commission.csv")

    if not os.path.exists(commission_csv):
        return {"status": "error", "message": "commission.csv not found."}

    df = pd.read_csv(commission_csv)
    if df.empty:
        return {"status": "error", "message": "commission.csv is empty."}

    matched_row = None
    deal_info = None
    for _, row in df.iterrows():
        deals_raw = row.get("deals")
        try:
            deals = json.loads(deals_raw) if isinstance(deals_raw, str) else []
        except Exception:
            deals = []
        for deal in deals:
            if str(deal.get("stock_number", "")).strip().lower() == stock_number.strip().lower():
                matched_row = row
                deal_info = deal
                break
        if deal_info:
            break

    if not deal_info:
        return {"status": "error", "message": f"No deal found for stock_number={stock_number}."}

    template = Template(
        """
        <html>
        <head><meta charset='utf-8'><title>Payout</title></head>
        <body>
          <h2>Imperial Cars - Commission Payout</h2>
          <p><strong>Salesperson:</strong> {{ salesperson }}</p>
          <p><strong>Week Ending:</strong> {{ week_ending }}</p>
          <hr/>
          <p><strong>Stock Number:</strong> {{ stock_number }}</p>
          <p><strong>Deal Number:</strong> {{ deal_number }}</p>
          <p><strong>Customer:</strong> {{ customer }}</p>
          <p><strong>Vehicle:</strong> {{ vehicle }}</p>
          <p><strong>Commission Amount:</strong> ${{ commission }}</p>
        </body>
        </html>
        """
    )

    html = template.render(
        salesperson=str(matched_row.get("salesperson_name", "")),
        week_ending=str(matched_row.get("week_ending", "")),
        stock_number=str(deal_info.get("stock_number", "")),
        deal_number=str(deal_info.get("deal_number", "")),
        customer=str(deal_info.get("customer_name", "")),
        vehicle=str(deal_info.get("vehicle_description", "")),
        commission=str(deal_info.get("commission_amount", 0) or 0),
    )

    out_path = os.path.join(data_dir, f"payout_{stock_number}.pdf")
    try:
        pdfkit.from_string(html, out_path)
    except Exception as exc:
        return {
            "status": "error",
            "message": "Unable to generate PDF. Ensure wkhtmltopdf is installed and available.",
            "details": str(exc),
        }

    return {"status": "ok", "path": out_path}


async def payout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /payout STOCK_NUMBER")
        return
    stock_number = context.args[0]
    result = await asyncio.to_thread(_generate_payout_pdf, stock_number)
    if result.get("status") != "ok":
        await update.message.reply_text(result.get("message", "Payout generation failed."))
        return
    await update.message.reply_text(f"Payout PDF generated: {result.get('path')}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.voice:
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_ogg:
        ogg_path = tmp_ogg.name
    wav_path = ogg_path.replace(".ogg", ".wav")

    try:
        await file.download_to_drive(custom_path=ogg_path)

        # Convert OGG -> WAV via ffmpeg.
        await asyncio.to_thread(
            subprocess.run,
            ["ffmpeg", "-i", ogg_path, "-acodec", "pcm_s16le", "-ar", "16000", wav_path, "-y"],
            check=True,
        )

        text = await asyncio.to_thread(transcribe_audio, wav_path)
        lead_data = await asyncio.to_thread(extract_lead_info, text, False)
        result = await asyncio.to_thread(process_lead_image_from_text, lead_data)

        await update.message.reply_text(
            "Lead added from voice input. "
            f"Customer: {result.get('data', {}).get('customer_name', 'Unknown')}"
        )
    except Exception as exc:
        await update.message.reply_text(f"Voice processing failed: {exc}")
    finally:
        for p in [ogg_path, wav_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    caption = (update.message.caption or "").strip()

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp_path = tmp.name

    try:
        await file.download_to_drive(custom_path=tmp_path)

        # If user is in trade-in flow, handle photo-based quote assistance.
        if context.user_data.get("awaiting_trade_in"):
            damage = await asyncio.to_thread(detect_damage, tmp_path)
            context.user_data["awaiting_trade_in"] = False
            await update.message.reply_text(
                "Photo received. Preliminary visual condition: "
                f"{damage}. Send VIN for a precise quote using /trade_in_quote."
            )
            return

        # If photo caption is an appraise command, run damage-aware appraisal.
        if caption.lower().startswith("/appraise"):
            parts = caption.split()[1:]
            await _run_appraise_reply(update, parts, image_path=tmp_path)
            return

        doc_type = caption.lower()
        if doc_type not in DOC_TYPES:
            await update.message.reply_text(
                "Unsupported or missing caption. Use one of: lead, insurance, cleanup, sold, commission, credit"
            )
            return

        result = await asyncio.to_thread(process_document_image, tmp_path, doc_type)
        if result.get("status") != "ok":
            await update.message.reply_text(result.get("message", "Document processing failed."))
            return

        await update.message.reply_text(
            f"Processed {doc_type} form successfully. Saved to {result.get('saved_to')}"
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    question = (update.message.text or "").strip()

    # Handle /trade_in_quote conversational step.
    if context.user_data.get("awaiting_trade_in"):
        vin = question.strip().upper()
        if len(vin) == 17:
            vin_data = await asyncio.to_thread(decode_vin, vin)
            if vin_data.get("status") != "ok":
                await update.message.reply_text("Could not decode VIN. Try again or send a clearer VIN/photo.")
                return

            cars = await asyncio.to_thread(_find_cars, f"{vin_data.get('make', '')} {vin_data.get('model', '')}", 1)
            baseline = float(cars[0].used_avg_price) if cars and cars[0].used_avg_price else 18000.0
            low = baseline * 0.8
            high = baseline * 0.92
            context.user_data["awaiting_trade_in"] = False
            await update.message.reply_text(
                f"Trade-in estimate for {vin_data.get('year')} {vin_data.get('make')} {vin_data.get('model')}:\n"
                f"${low:,.0f} - ${high:,.0f}\n"
                "Reply /schedule_test_drive to visit the dealership."
            )
            return

        await update.message.reply_text("Please send a valid 17-character VIN or upload a photo.")
        return

    # Handle /payment_calc multi-step flow.
    payment_flow = context.user_data.get("payment_flow")
    if payment_flow:
        step = payment_flow.get("step")
        data = payment_flow.setdefault("data", {})
        try:
            value = float(question)
        except ValueError:
            await update.message.reply_text("Please enter a numeric value.")
            return

        if step == "price":
            data["price"] = value
            payment_flow["step"] = "down"
            await update.message.reply_text("Enter down payment")
            return
        if step == "down":
            data["down"] = value
            payment_flow["step"] = "rate"
            await update.message.reply_text("Enter APR % (example: 6.9)")
            return
        if step == "rate":
            data["rate"] = value
            payment_flow["step"] = "term"
            await update.message.reply_text("Enter term in months (example: 60)")
            return
        if step == "term":
            term = int(value)
            monthly, total = await asyncio.to_thread(
                loan_calculator,
                data.get("price", 30000.0),
                data.get("down", 5000.0),
                data.get("rate", 6.9),
                term,
            )
            context.user_data.pop("payment_flow", None)
            await update.message.reply_text(f"Monthly: ${monthly:,.2f}\nTotal Loan Cost: ${total:,.2f}")
            return

    # Handle /schedule_test_drive flow.
    test_drive_flow = context.user_data.get("test_drive_flow")
    if test_drive_flow:
        text = question.lower()
        if text in {"today", "tomorrow", "this weekend"}:
            appointment = text.title()
        else:
            try:
                appointment = datetime.strptime(question, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                await update.message.reply_text("Use Today, Tomorrow, This Weekend, or YYYY-MM-DD.")
                return

        context.user_data.pop("test_drive_flow", None)
        await update.message.reply_text(f"Test drive scheduled for {appointment}. A salesperson will confirm shortly.")
        return

    prompt = (
        "You are Imperial Cars sales assistant. Reply briefly and actionably. "
        "If relevant, suggest next command among /ask /specs /compare /price_check /trade_in_quote /payment_calc /my_jobs.\n\n"
        f"User message: {question}"
    )
    answer = await _call_ollama(prompt)
    await update.message.reply_text(answer[:3900])


async def followup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send preference-based follow-up using the same backend API endpoint."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /followup <customer_id>\n\n"
            "Sends follow-up via enabled customer channels."
        )
        return

    try:
        customer_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid customer ID. Use: /followup <customer_id>")
        return

    try:
        api_url = _env("API_BASE_URL", "http://localhost:8000").rstrip("/")

        def _post_followup() -> dict[str, Any]:
            r = requests.post(
                f"{api_url}/api/followup/{customer_id}",
                json={},
                timeout=30,
            )
            return r.json()

        result = await asyncio.to_thread(_post_followup)

        if result.get("status") == "completed":
            await update.message.reply_text(
                f"✓ Follow-up sent successfully!\n\n"
                f"SMS: {result.get('sms_status')}\n"
                f"WhatsApp: {result.get('whatsapp_status')}\n"
                f"Voice: {result.get('voice_status')}\n"
                f"Email: {result.get('email_status')}"
            )
        elif result.get("status") == "partial":
            await update.message.reply_text(
                f"⚠ Follow-up partially sent:\n\n"
                f"SMS: {result.get('sms_status')}\n"
                f"WhatsApp: {result.get('whatsapp_status')}\n"
                f"Voice: {result.get('voice_status')}\n"
                f"Email: {result.get('email_status')}\n\n"
                f"Summary: {result.get('summary')}"
            )
        else:
            await update.message.reply_text(
                f"✗ Follow-up failed: {result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        logger.exception("followup_cmd_error")
        await update.message.reply_text(f"Error sending follow-up: {str(e)}")


async def prefs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show or update customer channel preferences via backend API.

    Usage:
      /prefs <customer_id>
      /prefs <customer_id> set <sms|whatsapp|email|voice> <on|off> [contact]
    """
    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/prefs <customer_id>\n"
            "/prefs <customer_id> set <sms|whatsapp|email|voice> <on|off> [contact]"
        )
        return

    try:
        customer_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid customer ID.")
        return

    api_url = _env("API_BASE_URL", "http://localhost:8000").rstrip("/")

    def _get_prefs() -> dict[str, Any]:
        r = requests.get(f"{api_url}/api/customer-preferences/{customer_id}", timeout=30)
        return r.json() if r.ok else {"status": "failed", "error": r.text}

    def _put_prefs(payload: dict[str, Any]) -> dict[str, Any]:
        r = requests.put(f"{api_url}/api/customer-preferences/{customer_id}", json=payload, timeout=30)
        return r.json() if r.ok else {"status": "failed", "error": r.text}

    try:
        current = await asyncio.to_thread(_get_prefs)
        current_prefs = current.get("preferences", []) if isinstance(current, dict) else []

        if len(context.args) == 1:
            if not current_prefs:
                await update.message.reply_text("No saved preferences for this customer.")
                return
            lines = [f"Preferences for customer {customer_id}:"]
            for p in current_prefs:
                lines.append(
                    f"- {p.get('channel')}: enabled={p.get('is_enabled')} contact={p.get('contact_value') or '-'}"
                )
            await update.message.reply_text("\n".join(lines))
            return

        if len(context.args) < 4 or context.args[1].lower() != "set":
            await update.message.reply_text(
                "Usage: /prefs <customer_id> set <sms|whatsapp|email|voice> <on|off> [contact]"
            )
            return

        channel = context.args[2].strip().lower()
        state = context.args[3].strip().lower()
        if channel not in {"sms", "whatsapp", "email", "voice"}:
            await update.message.reply_text("Channel must be one of: sms, whatsapp, email, voice.")
            return
        if state not in {"on", "off", "true", "false", "1", "0"}:
            await update.message.reply_text("State must be on/off.")
            return

        enabled = state in {"on", "true", "1"}
        contact = " ".join(context.args[4:]).strip() if len(context.args) > 4 else None

        pref_map: dict[str, dict[str, Any]] = {
            "sms": {"channel": "sms", "is_enabled": False, "contact_value": None},
            "whatsapp": {"channel": "whatsapp", "is_enabled": False, "contact_value": None},
            "email": {"channel": "email", "is_enabled": False, "contact_value": None},
            "voice": {"channel": "voice", "is_enabled": False, "contact_value": None},
        }
        for p in current_prefs:
            ch = str(p.get("channel", "")).strip().lower()
            if ch in pref_map:
                pref_map[ch] = {
                    "channel": ch,
                    "is_enabled": bool(p.get("is_enabled", False)),
                    "contact_value": p.get("contact_value"),
                }

        pref_map[channel]["is_enabled"] = enabled
        if contact:
            pref_map[channel]["contact_value"] = contact

        payload = {"preferences": list(pref_map.values())}
        updated = await asyncio.to_thread(_put_prefs, payload)
        if updated.get("status") == "updated":
            await update.message.reply_text(
                f"Updated {channel} preference for customer {customer_id}: enabled={enabled}, contact={pref_map[channel].get('contact_value') or '-'}"
            )
        else:
            await update.message.reply_text(f"Preference update failed: {updated.get('error', updated)}")
    except Exception as exc:
        logger.exception("prefs_cmd_error")
        await update.message.reply_text(f"Error handling preferences: {exc}")


def main() -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("specs", specs_cmd))
    app.add_handler(CommandHandler("compare", compare_cmd))
    app.add_handler(CommandHandler("price_check", price_check_cmd))
    app.add_handler(CommandHandler("trade_in_quote", trade_in_quote_cmd))
    app.add_handler(CommandHandler("payment_calc", payment_calc_cmd))
    app.add_handler(CommandHandler("show_chart", show_chart_cmd))
    app.add_handler(CommandHandler("my_jobs", my_jobs_cmd))
    app.add_handler(CommandHandler("prefs", prefs_cmd))
    app.add_handler(CommandHandler("followup", followup_cmd))
    app.add_handler(CommandHandler("schedule_test_drive", schedule_test_drive_cmd))
    app.add_handler(CommandHandler("briefing", briefing_cmd))
    app.add_handler(CommandHandler("scoreleads", scoreleads_cmd))
    app.add_handler(CommandHandler("rankleads", rankleads_cmd))
    app.add_handler(CommandHandler("appraise", appraise_cmd))
    app.add_handler(CommandHandler("payout", payout_cmd))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(on_bot_error)

    logger.info("Imperial Cars bot starting")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
