import os
from typing import Optional, Any, Dict, List, Union

import httpx
from dotenv import load_dotenv


load_dotenv()


def upload_and_return_url(
	file_path: Optional[str] = None,
	*,
	filename: str = "products.json",
	content: Optional[Union[bytes, str]] = None,
) -> str:
	print(f"[Toolswift] upload_and_return_url started. file_path={file_path}")


	api_base = (
		os.getenv("TOOLSWIFT_URL")
		or os.getenv("TOOLSWIFT_API_BASE")
		or "https://demo.api.toolswift.ca"
	).rstrip("/")
	store_key = os.getenv("TOOLSWIFT_STORE_KEY")
	bearer_token = os.getenv("TOOLSWIFT_BEARER_TOKEN")
	if not store_key:
		raise ValueError("TOOLSWIFT_STORE_KEY is not set in environment variables")
	if not bearer_token:
		raise ValueError("TOOLSWIFT_BEARER_TOKEN is not set in environment variables")

	url = f"{api_base}/file-proccesor/"
	headers = {
		"x-store-key": store_key,
		"Authorization": f"Bearer {bearer_token}",
	}

	print(f"[Toolswift] Uploading file to {url} ...")
	if content is not None:
		data_bytes = content.encode("utf-8") if isinstance(content, str) else content
		files = {"file": (filename, data_bytes, "application/json")}
		resp = httpx.post(url, headers=headers, files=files, timeout=120.0)
		resp.raise_for_status()
	else:
		if not file_path:
			raise ValueError("Either file_path or content must be provided")
		filename = os.path.basename(file_path)
		with open(file_path, "rb") as fh:
			files = {"file": (filename, fh, "application/json")}
			resp = httpx.post(url, headers=headers, files=files, timeout=120.0)
			resp.raise_for_status()

	try:
		payload = resp.json()
	except Exception:
		print(f"[Toolswift] Unexpected non-JSON response: {resp.text[:500]}")
		raise

	location = payload.get("uploadedFileUrl") or payload.get("location") or payload.get("url")
	if not location:
		raise ValueError(f"[Toolswift] Upload did not return a location/url. Response: {payload}")

	print(f"[Toolswift] upload_and_return_url finished. location={location}")
	return location


def start_toolswift_upload_with_json(
	priced_catalog: List[Dict[str, Any]],
	product_count: int,
	location_url: str = None,
) -> Dict[str, Any]:
	print(f"[Toolswift] start_toolswift_upload_with_json started. product_count={product_count}")

	api_base = (
		os.getenv("TOOLSWIFT_URL")
		or os.getenv("TOOLSWIFT_API_BASE")
		or "https://demo.api.toolswift.ca"
	).rstrip("/")
	store_key = os.getenv("TOOLSWIFT_STORE_KEY")
	bearer_token = os.getenv("TOOLSWIFT_BEARER_TOKEN")
	if not store_key:
		raise ValueError("TOOLSWIFT_STORE_KEY is not set in environment variables")
	if not bearer_token:
		raise ValueError("TOOLSWIFT_BEARER_TOKEN is not set in environment variables")

	headers = {
		"x-store-key": store_key,
		"Authorization": f"Bearer {bearer_token}",
		"Content-Type": "application/json",
	}
	url = f"{api_base}/products/json-bulk-upload"
	payload = {
			"Location": location_url,
			"upsert": True ,
		}
	print("[Toolswift] Sending location payload to Toolswift API ...")
	response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
	response.raise_for_status()
	print("[Toolswift] Upload request accepted by Toolswift API")
	print(f"[Toolswift] start_toolswift_upload_with_json finished (location mode).")
	return response.json()

