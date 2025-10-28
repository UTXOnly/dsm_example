import os
import json
import logging
from ddtrace import tracer, patch

patch(fastapi=True)

from fastapi import FastAPI, Body, HTTPException
from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.data_streams import set_produce_checkpoint

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT = os.getenv("GCP_PROJECT", "your-gcp-project")
TOPIC = os.getenv("PUBSUB_TOPIC", "jobs-topic")
DD_SERVICE = os.getenv("DD_SERVICE", "jobs-api")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT, TOPIC)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    try:
        publisher.get_topic(request={"topic": topic_path})
        logger.info(f"Connected to topic: {TOPIC}")
    except Exception as e:
        logger.error(f"Topic verification failed: {e}")

@app.post("/jobs")
def enqueue_job(payload: dict = Body(...)):
    attributes: dict[str, str] = {}
    
    current_span = tracer.current_span()
    if current_span:
        HTTPPropagator.inject(current_span.context, attributes)
    
    set_produce_checkpoint("pubsub", TOPIC, attributes.setdefault)
    
    attributes["job_type"] = payload.get("type", "unknown")
    body = json.dumps(payload).encode("utf-8")
    
    with tracer.trace("pubsub.publish", resource=TOPIC, service=DD_SERVICE) as span:
        span.set_tag("messaging.system", "pubsub")
        span.set_tag("messaging.destination", TOPIC)
        span.set_tag("job.type", payload.get("type", "unknown"))
        
        future = publisher.publish(topic_path, data=body, **attributes)
        message_id = future.result()
        
        span.set_tag("messaging.message_id", message_id)
    
    return {"status": "queued", "id": message_id}
