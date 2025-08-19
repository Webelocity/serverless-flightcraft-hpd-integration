import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from starlette.concurrency import run_in_threadpool

from hpd.api import get_full_catalog
from hpd.pricing import compute_priced_catalog
from hpd.toolswift import start_toolswift_upload_with_json, upload_and_return_url
from hpd.email import notify_integration_started, notify_error, send_email

DISABLE_INTERNAL_SCHEDULER = os.getenv("DISABLE_INTERNAL_SCHEDULER", "false").lower() == "true"
SCHEDULE_CRON = os.getenv("SCHEDULE_CRON", "")            # e.g. "0 * * * *"

# Interval configuration supports days/hours/minutes.
# Default behavior (for backward compatibility): 60 minutes if days and hours are both 0
SCHEDULE_EVERY_DAYS = int(os.getenv("SCHEDULE_EVERY_DAYS", "0"))
SCHEDULE_EVERY_HOURS = int(os.getenv("SCHEDULE_EVERY_HOURS", "0"))
if "SCHEDULE_EVERY_MINUTES" in os.environ:
	SCHEDULE_EVERY_MINUTES = int(os.environ["SCHEDULE_EVERY_MINUTES"])  # explicit user choice
else:
	SCHEDULE_EVERY_MINUTES = 60 if (SCHEDULE_EVERY_DAYS == 0 and SCHEDULE_EVERY_HOURS == 0) else 0

scheduler = AsyncIOScheduler()

def send_integration_started_email(total_count: int) -> None:
	"""Send an email notification that the integration has started."""
	print(f"[Notify] send_integration_started_email started. total_count={total_count}")
	try:
		notify_integration_started(total_count)
		print("[Notify] Integration start email sent.")
	except Exception as e:
		print(f"[Notify] Failed to send start email: {e}")

def run_job() -> dict:
	print("[Job] run_job started.")
	products = get_full_catalog()
	print(f"[Job] Retrieved catalog. count={len(products)}")

	priced = compute_priced_catalog(products)
	print(f"[Job] Computed priced catalog. count={len(priced)}")

	first_product = priced[0]
	print(f"[Job] First product: {first_product}")

	# Kick off Toolswift initiation with URL location if available, else fallback to JSON
	try:
		try:
			send_integration_started_email(len(priced))
		except Exception as e:
			print(f"[Notify] Failed to send start email: {e}")

		print("[Job] Uploading priced catalog to file-processor to obtain location ...")
		# Upload in-memory JSON to obtain a URL location
		import json as _json
		location_url = upload_and_return_url(filename="priced_catalog.json", content=_json.dumps(priced))
		print(f"[Job] Obtained location: {location_url}")

		print("[Job] Starting Toolswift upload (location mode) ...")
		resp = start_toolswift_upload_with_json(priced, len(priced), location_url=location_url)

		print(f"[Job] Toolswift upload finished. response_summary={str(resp)[:500]}")
	except Exception as e:
		# Non-fatal: log and continue
		print(f"[Toolswift] Failed to initiate upload: {e}")
		try:
			notify_error("Toolswift initiation failed", e)
		except Exception as ne:
			print(f"[Notify] Failed to send error email: {ne}")

	result = {
		"count": len(priced),
	}
	print(f"[Job] run_job finished. result={result}")
	return result

@asynccontextmanager
async def lifespan(app: FastAPI):
	# startup
	print("[App] lifespan startup started.")
	if not DISABLE_INTERNAL_SCHEDULER:
		print("[App] Configuring internal scheduler ...")
		if SCHEDULE_CRON:
			scheduler.add_job(
				run_job,
				CronTrigger.from_crontab(SCHEDULE_CRON),
				id="pricedump",
				replace_existing=True,
			)
			print(f"[App] Scheduler configured with CRON: {SCHEDULE_CRON}")
		else:
			scheduler.add_job(
				run_job,
				IntervalTrigger(
					days=SCHEDULE_EVERY_DAYS,
					hours=SCHEDULE_EVERY_HOURS,
					minutes=SCHEDULE_EVERY_MINUTES,
				),
				id="pricedump",
				replace_existing=True,
			)
			print(f"[App] Scheduler configured with interval: d={SCHEDULE_EVERY_DAYS}, h={SCHEDULE_EVERY_HOURS}, m={SCHEDULE_EVERY_MINUTES}")
		scheduler.start()
		print("[App] Scheduler started.")
	try:
		print("[App] lifespan startup finished.")
		yield
	finally:
		# shutdown
		print("[App] lifespan shutdown started.")
		if not DISABLE_INTERNAL_SCHEDULER and scheduler.running:
			scheduler.shutdown()
			print("[App] Scheduler shutdown complete.")
		print("[App] lifespan shutdown finished.")

app = FastAPI(title="HPD Pricing Scheduler", lifespan=lifespan)

@app.get("/health")
async def health():
	print("[API] /health called.")
	return {"status": "ok"}

@app.post("/run-now")
async def run_now():
	print("[API] /run-now invoked. Running job in threadpool ...")
	result = await run_in_threadpool(run_job)
	print("[API] /run-now finished.")
	return result

@app.post("/test-email")
async def test_email(to: str = ""):
	"""Send a test email using current SMTP settings.

	- Optional query param `to` supports comma or semicolon-separated recipients.
	- If omitted, uses NOTIFY_EMAIL_TO/CC/BCC from environment.
	"""
	print(f"[API] /test-email called. to={to!r}")
	try:
		recipients = None
		if to:
			recipients = [p.strip() for p in to.replace(";", ",").split(",") if p.strip()]
		resp = await run_in_threadpool(
			send_email,
			"HPD Integration Test Email",
			"This is a test email from HPD Pricing Scheduler.",
			to=recipients,
		)
		print("[API] /test-email sent successfully.")
		return {"ok": True, "summary": resp}
	except Exception as e:
		print(f"[API] /test-email failed: {e}")
		return {"ok": False, "error": str(e)}

@app.get("/status")
async def status():
	print("[API] /status called.")
	# If the internal scheduler is disabled, report that status
	if DISABLE_INTERNAL_SCHEDULER:
		return {
			"scheduled": False,
			"message": "Internal scheduler is disabled",
		}

	job = scheduler.get_job("pricedump")
	if job is None:
		return {
			"scheduled": False,
			"message": "No scheduled job found",
		}

	next_run = job.next_run_time
	if next_run is None:
		return {
			"scheduled": True,
			"next_run": None,
			"seconds_until_next_run": None,
			"message": "Next run time is not available yet",
		}

	now_utc = datetime.now(timezone.utc)
	if next_run.tzinfo is None:
		next_run_utc = next_run.replace(tzinfo=timezone.utc)
	else:
		next_run_utc = next_run.astimezone(timezone.utc)

	seconds_left = int((next_run_utc - now_utc).total_seconds())
	if seconds_left < 0:
		seconds_left = 0

	time_until_hms = f"{seconds_left // 3600:02}:{(seconds_left % 3600) // 60:02}:{seconds_left % 60:02}"

	formatted_date_time = f"{next_run_utc.strftime('%d/%m/%Y')} {next_run_utc.strftime('%H:%M')}"

	return {
		"scheduled": True,
		"next_run": formatted_date_time,
		"next_run_iso": next_run_utc.isoformat(),
		"seconds_until_next_run": seconds_left,
		"minutes_until_next_run": round(seconds_left / 60, 2),
		"time_until_next_run": time_until_hms,
	}