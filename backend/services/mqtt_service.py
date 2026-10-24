# Agent 2 — GIAI ĐOẠN 2. Payload dùng chung cho cả hai nhánh: {"decision": "granted"|"denied"}
TOPIC_DECISION = "door/access/decision"
def publish_decision(decision: str):
    raise NotImplementedError
