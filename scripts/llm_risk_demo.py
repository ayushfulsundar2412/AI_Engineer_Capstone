import json
import logging

from app.llm_core import ask_structured
from app.llm_core.models import RiskAssessment

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

resource = {
    "resource_type": "security_group",
    "name": "open-ssh",
    "config": {"inbound": [{"port": 22, "cidr": "0.0.0.0/0"}]},
}

result = ask_structured(
    system="You review cloud resources for security risk.",
    user=json.dumps(resource),
    model=RiskAssessment,
)
print(result.model_dump_json(indent=2))