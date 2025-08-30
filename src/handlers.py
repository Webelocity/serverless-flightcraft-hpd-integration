"""
Lambda handlers for HPD Pricing Integration
Replaces the FastAPI endpoints with individual Lambda functions
"""

import json
import os
import boto3
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Import the existing HPD modules
from hpd.api import get_full_catalog
from hpd.pricing import compute_priced_catalog
from hpd.toolswift import upload_and_return_url, start_toolswift_upload_with_json
from hpd.email import send_email, notify_integration_started, notify_error


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body)
    }


def health_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Health check endpoint - replaces GET /health"""
    print("[API] /health called.")
    return create_response(200, {"status": "ok"})


def run_job() -> Dict[str, Any]:
    """Core business logic - same as original run_job function"""
    print("[Job] run_job started.")
    
    try:
        # Get catalog from HPD API
        products = get_full_catalog()  
        print(f"[Job] Retrieved catalog. count={len(products)}")

        # Compute pricing
        priced = compute_priced_catalog(products)
        print(f"[Job] Computed priced catalog. count={len(priced)}")

        # Log first product for debugging
        if priced:
            first_product = priced[0]
            print(f"[Job] First product: {first_product}")

        # Send integration started email
        try:
            notify_integration_started(len(priced))
            print("[Notify] Integration start email sent.")
        except Exception as e:
            print(f"[Notify] Failed to send start email: {e}")

        # Upload to S3 and get URL for Toolswift
        try:
            print("[Job] Uploading priced catalog to S3...")
            
            # Upload to S3 instead of file-processor
            s3_client = boto3.client('s3')
            bucket_name = os.environ['S3_BUCKET_NAME']
            
            # Create filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            s3_key = f"pricing_data/priced_catalog_{timestamp}.json"
            
            # Upload JSON to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=json.dumps(priced),
                ContentType='application/json'
            )
            
            # Create pre-signed URL for Toolswift to access the file
            location_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=3600  # 1 hour
            )
            
            print(f"[Job] Uploaded to S3: s3://{bucket_name}/{s3_key}")
            print(f"[Job] Generated pre-signed URL: {location_url}")

            # Start Toolswift upload
            print("[Job] Starting Toolswift upload (location mode) ...")
            resp = start_toolswift_upload_with_json(priced, len(priced), location_url=location_url)
            print(f"[Job] Toolswift upload finished. response_summary={str(resp)[:500]}")
            
        except Exception as e:
            print(f"[Toolswift] Failed to initiate upload: {e}")
            try:
                notify_error("Toolswift initiation failed", e)
            except Exception as ne:
                print(f"[Notify] Failed to send error email: {ne}")

        result = {
            "count": len(priced),
            "s3_key": s3_key if 's3_key' in locals() else None,
            "timestamp": timestamp if 'timestamp' in locals() else None
        }
        print(f"[Job] run_job finished. result={result}")
        return result
        
    except Exception as e:
        print(f"[Job] run_job failed: {e}")
        try:
            notify_error("Job execution failed", e)
        except Exception as ne:
            print(f"[Notify] Failed to send error email: {ne}")
        raise


def run_now_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Manual job trigger - replaces POST /run-now"""
    print("[API] /run-now invoked. Running job...")
    
    try:
        result = run_job()
        print("[API] /run-now finished successfully.")
        return create_response(200, result)
    except Exception as e:
        print(f"[API] /run-now failed: {e}")
        return create_response(500, {
            "error": "Job execution failed",
            "message": str(e)
        })


def test_email_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Test email function - replaces POST /test-email"""
    print(f"[API] /test-email called.")
    
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        to_param = query_params.get('to', '')
        
        recipients = None
        if to_param:
            recipients = [p.strip() for p in to_param.replace(";", ",").split(",") if p.strip()]

        result = send_email(
            "HPD Integration Test Email",
            "This is a test email from HPD Pricing Scheduler (Lambda version).",
            to=recipients,
        )
        
        print("[API] /test-email sent successfully.")
        return create_response(200, {"ok": True, "summary": result})
        
    except Exception as e:
        print(f"[API] /test-email failed: {e}")
        return create_response(500, {
            "ok": False,
            "error": str(e)
        })


def status_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Status check - replaces GET /status"""
    print("[API] /status called.")
    
    try:
        # In Lambda, we don't have an internal scheduler
        # Instead, we check the EventBridge rule
        events_client = boto3.client('events')
        
        # Try to get the rule information
        try:
            stack_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').replace('-StatusFunction', '')
            rule_name = f"{stack_name}-ScheduledJobRule"
            
            response = events_client.describe_rule(Name=rule_name)
            
            return create_response(200, {
                "scheduled": True,
                "rule_name": rule_name,
                "schedule_expression": response.get('ScheduleExpression'),
                "state": response.get('State'),
                "description": response.get('Description'),
                "message": "Scheduled via EventBridge"
            })
            
        except Exception as rule_error:
            print(f"[Status] Could not get rule info: {rule_error}")
            return create_response(200, {
                "scheduled": True,
                "message": "Running on EventBridge schedule (rule details unavailable)",
                "note": "This is the Lambda/SAM version - no internal scheduler"
            })
            
    except Exception as e:
        print(f"[API] /status failed: {e}")
        return create_response(500, {
            "error": "Status check failed",
            "message": str(e)
        })


def scheduled_job_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """EventBridge scheduled job handler - replaces APScheduler"""
    print("[Scheduled] Scheduled job triggered by EventBridge")
    
    try:
        result = run_job()
        print("[Scheduled] Scheduled job completed successfully")
        return {
            "statusCode": 200,
            "body": result
        }
    except Exception as e:
        print(f"[Scheduled] Scheduled job failed: {e}")
        return {
            "statusCode": 500,
            "body": {
                "error": "Scheduled job failed",
                "message": str(e)
            }
        }
