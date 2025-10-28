# Datadog DSM with GCP Pub/Sub

Producer-consumer example using Datadog Data Streams Monitoring with GCP Pub/Sub.

## Setup

### Prerequisites

- GCP Project with Pub/Sub enabled
- Service account with Pub/Sub permissions
- Datadog API key
- Docker & Docker Compose

### Configuration

Create `.env`:

```bash
GCP_PROJECT=your-project-id
PUBSUB_TOPIC=jobs-topic
PUBSUB_SUBSCRIPTION=jobs-sub
DD_SITE=datadoghq.com
DD_API_KEY=your-datadog-api-key
DD_DATA_STREAMS_ENABLED=true
```

Add `gcp-key.json` with your service account credentials.

### GCP Resources

```bash
gcloud pubsub topics create jobs-topic
gcloud pubsub subscriptions create jobs-sub --topic=jobs-topic
```

### Run

```bash
docker-compose up -d
```

## Instrumentation

### Producer

```python
from ddtrace import tracer
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.data_streams import set_produce_checkpoint

# When publishing:
attributes: dict[str, str] = {}

# Inject trace context into message attributes
current_span = tracer.current_span()
if current_span:
    HTTPPropagator.inject(current_span.context, attributes)

# Set DSM produce checkpoint
set_produce_checkpoint("pubsub", TOPIC, attributes.setdefault)

# Trace the publish operation
with tracer.trace("pubsub.publish", resource=TOPIC) as span:
    span.set_tag("messaging.system", "pubsub")
    span.set_tag("messaging.destination", TOPIC)
    future = publisher.publish(topic_path, data=body, **attributes)
    message_id = future.result()
    span.set_tag("messaging.message_id", message_id)
```

### Consumer

```python
from ddtrace import tracer
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.data_streams import set_consume_checkpoint

# When receiving:
attributes = dict(message.attributes)

# Extract trace context from message attributes
ctx = HTTPPropagator.extract(attributes)

# Set DSM consume checkpoint
set_consume_checkpoint("pubsub", SUBSCRIPTION, attributes.get)

# Activate the extracted context
if ctx:
    tracer.context_provider.activate(ctx)

try:
    # Trace the consume operation
    with tracer.trace("pubsub.consume", resource=SUBSCRIPTION) as consume_span:
        consume_span.set_tag("messaging.system", "pubsub")
        consume_span.set_tag("messaging.message_id", message.message_id)
        
        payload = json.loads(message.data.decode("utf-8"))
        
        # Trace your processing logic
        with tracer.trace("pubsub.process", resource=SUBSCRIPTION):
            # process message
            pass
            
        message.ack()
finally:
    if ctx:
        tracer.context_provider.activate(None)
```

### Environment Variables

Set in `docker-compose.yaml`:

```yaml
DD_SERVICE=jobs-api  # or jobs-consumer
DD_ENV=dsm
DD_DATA_STREAMS_ENABLED=true
DD_AGENT_HOST=datadog-agent
DD_TRACE_SAMPLE_RATE=1.0
```

## Testing

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "email", "to": "user@example.com"}'
```

Or use the load test script:

```bash
./load-test.sh
```

## Verification

Check agent status:

```bash
docker exec datadog-agent agent status
```

View in Datadog:
- APM Traces: https://app.datadoghq.com/apm/traces
- Data Streams: https://app.datadoghq.com/data-streams



https://github.com/user-attachments/assets/3cc24076-3721-429e-80de-fe6ba612ca7e


