import os
import json
import logging
from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions
from ddtrace import tracer
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.data_streams import set_consume_checkpoint

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT = os.getenv("GCP_PROJECT", "your-gcp-project")
SUBSCRIPTION = os.getenv("PUBSUB_SUBSCRIPTION", "jobs-sub")
DD_SERVICE = os.getenv("DD_SERVICE", "jobs-consumer")

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT, SUBSCRIPTION)

def process_message(message: pubsub_v1.subscriber.message.Message):
    attributes = dict(message.attributes)
    ctx = HTTPPropagator.extract(attributes)
    set_consume_checkpoint("pubsub", SUBSCRIPTION, attributes.get)
    
    if ctx:
        tracer.context_provider.activate(ctx)
    
    try:
        with tracer.trace("pubsub.consume", resource=SUBSCRIPTION, service=DD_SERVICE) as span:
            span.set_tag("messaging.system", "pubsub")
            span.set_tag("messaging.destination", SUBSCRIPTION)
            span.set_tag("messaging.message_id", message.message_id)
            
            payload = json.loads(message.data.decode("utf-8"))
            span.set_tag("job.type", payload.get("type"))
            
            with tracer.trace("pubsub.process", resource=SUBSCRIPTION, service=DD_SERVICE) as process_span:
                process_span.set_tag("job.type", payload.get("type"))
                process_span.set_tag("messaging.message_id", message.message_id)
                
                # Process message here
            
            message.ack()
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        message.nack()
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        message.nack()
    finally:
        if ctx:
            tracer.context_provider.activate(None)

def verify_subscription():
    try:
        sub = subscriber.get_subscription(request={"subscription": subscription_path})
        logger.info(f"Connected to subscription: {SUBSCRIPTION}")
        return True
    except Exception as e:
        logger.error(f"Subscription verification failed: {e}")
        return False

def main():
    if not verify_subscription():
        return 1
    
    flow_control = pubsub_v1.types.FlowControl(max_messages=10)
    streaming_pull_future = subscriber.subscribe(
        subscription_path,
        callback=process_message,
        flow_control=flow_control
    )
    
    logger.info("Consumer started")
    
    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        streaming_pull_future.result()
    except Exception as e:
        logger.error(f"Consumer error: {e}")
        streaming_pull_future.cancel()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
