import os
import json
from pathlib import Path
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

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data"))

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

# Toggle saving generated JSON files to disk (set to false in production)
SAVE_OUTPUT_FILES = os.getenv("SAVE_OUTPUT_FILES", "false").lower() == "true"

scheduler = AsyncIOScheduler()

def ensure_output_dir():
	print("[App] ensure_output_dir started.")
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	print(f"[App] ensure_output_dir finished. dir={OUTPUT_DIR}")

def send_integration_started_email(total_count: int) -> None:
	"""Placeholder email notification when integration starts.

	In production, replace this with actual email sending (SMTP/API).
	"""
	print(f"[Notify] send_integration_started_email started. total_count={total_count}")
	recipient = os.getenv("NOTIFY_EMAIL_TO", "")
	print(f"[Notify] Integration started for {total_count} products. To: {recipient}")
	print("[Notify] send_integration_started_email finished.")

def run_job() -> dict:
	print("[Job] run_job started.")
	products = get_full_catalog()
	print(f"[Job] Retrieved catalog. count={len(products)}")

	priced = compute_priced_catalog(products)
	print(f"[Job] Computed priced catalog. count={len(priced)}")

	ensure_output_dir()

	ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
	temp_file = OUTPUT_DIR / f"HPD_API_PRODUCTS_PRICED_{ts}.json"
	print(f"[Job] Writing priced catalog to temp file: {temp_file}")
	with open(temp_file, "w", encoding="utf-8") as f:
		json.dump(priced, f, indent=2, ensure_ascii=False)
	print("[Job] Temp file write complete.")

	remote_location = None
	try:
		print("[Job] Uploading temp file to file-processor to get S3 URL ...")
		remote_location = upload_and_return_url(str(temp_file))
		print(f"[Job] Upload complete. remote_location={remote_location}")
	except Exception as e:
		print(f"[Job] Upload failed: {e}")
		# Keep the local file for debugging if upload fails
	else:
		if not SAVE_OUTPUT_FILES:
			try:
				print(f"[Job] Deleting temp file (SAVE_OUTPUT_FILES=false): {temp_file}")
				temp_file.unlink(missing_ok=True)
				print("[Job] Temp file deleted.")
			except Exception as e:
				print(f"[Job] Failed to delete temp file: {e}")
		else:
			print(f"[Job] Keeping file on disk (SAVE_OUTPUT_FILES=true): {temp_file}")

	# Kick off Toolswift initiation with URL location if available, else fallback to JSON
	try:
		try:
			send_integration_started_email(len(priced))
		except Exception as e:
			print(f"[Notify] Failed to send start email: {e}")

		if remote_location:
			print("[Job] Starting Toolswift upload (location mode) ...")
			resp = start_toolswift_upload_with_json(priced, len(priced), location_url=remote_location)
		else:
			print("[Job] Starting Toolswift upload (json mode fallback) ...")
			resp = start_toolswift_upload_with_json(priced, len(priced))

		print(f"[Job] Toolswift upload finished. response_summary={str(resp)[:500]}")
	except Exception as e:
		# Non-fatal: log and continue
		print(f"[Toolswift] Failed to initiate upload: {e}")

	result = {
		"count": len(priced),
		"file": str(temp_file) if (SAVE_OUTPUT_FILES and temp_file.exists()) else None,
		"saved_files": SAVE_OUTPUT_FILES,
		"location_url": remote_location,
	}
	print(f"[Job] run_job finished. result={result}")
	return result

@asynccontextmanager
async def lifespan(app: FastAPI):
	# startup
	print("[App] lifespan startup started.")
	ensure_output_dir()
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