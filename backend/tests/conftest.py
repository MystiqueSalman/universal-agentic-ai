import os

# Tests must be deterministic and offline: force the local (template)
# planner/executor. Production uses the Model Router when a key is configured.
os.environ["UAA_DISABLE_LLM"] = "1"
