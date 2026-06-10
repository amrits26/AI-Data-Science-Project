# DeepSeek vs Current Model Benchmark

## Aggregate Metrics

| Profile | Count | Avg Latency (ms) | Vehicle Ref Rate | Spec Accuracy Rate | Hallucination Rate | Source Attribution Rate | Avg Fluency | Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 12 | 6091.64 | 0.25 | 0.0 | 0.167 | 1.0 | 4.75 | 0.564 |
| deepseek | 12 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.07 |

## Recommendation

**Keep current model**

## Per Query Snapshot

| Query | Profile | Latency (ms) | Source | Vehicle Ref | Spec Accuracy | Hallucination | Source Attribution | Fluency |
|---|---|---:|---|---:|---:|---:|---:|---:|
| Do you have a blue Ford F-150 with a tow package? | current | 24045.59 | knowledge_base | 0 | 0 | 1 | 1 | 2.0 |
| Compare the Ford F-150 and Chevy Colorado for towing capacity and fuel economy. | current | 4951.41 | multi_source | 1 | 0 | 1 | 1 | 5.0 |
| Show me SUVs with 3rd row seating under $35,000. | current | 4243.34 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| What's the difference between AWD and 4WD? | current | 4265.69 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| How safe is the 2024 Honda CR-V? | current | 4951.78 | multi_source | 1 | 0 | 0 | 1 | 5.0 |
| Which truck on your lot can tow my 8,000 lb boat and has the best fuel economy? | current | 4216.87 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| Is the 2023 Toyota Camry reliable for long-term ownership? | current | 4850.4 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| Tell me about the cheapest truck you have. | current | 4175.04 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| What's the starting MSRP for a Chevrolet Traverse? | current | 4199.14 | multi_source | 1 | 0 | 0 | 1 | 5.0 |
| Help me pick between GMC and Ford for a work truck. | current | 4159.29 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| I need a car that fits 3 car seats, has AWD, and gets good gas mileage. | current | 4211.65 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| Does a used 2022 Lexus RX hold its resale value? | current | 4829.48 | knowledge_base | 0 | 0 | 0 | 1 | 5.0 |
| Do you have a blue Ford F-150 with a tow package? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Compare the Ford F-150 and Chevy Colorado for towing capacity and fuel economy. | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Show me SUVs with 3rd row seating under $35,000. | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| What's the difference between AWD and 4WD? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| How safe is the 2024 Honda CR-V? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Which truck on your lot can tow my 8,000 lb boat and has the best fuel economy? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Is the 2023 Toyota Camry reliable for long-term ownership? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Tell me about the cheapest truck you have. | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| What's the starting MSRP for a Chevrolet Traverse? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Help me pick between GMC and Ford for a work truck. | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| I need a car that fits 3 car seats, has AWD, and gets good gas mileage. | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
| Does a used 2022 Lexus RX hold its resale value? | deepseek | 0.0 |  | 0 | 0 | 1 | 0 | 1.0 |
