import json
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # reads .env into environment variables
engine = create_engine(os.environ["DATABASE_URL"])

with engine.begin() as conn:  # begin() = start a transaction, commit on success
    scan_id = conn.execute(
        text("INSERT INTO scans (account_id, region) VALUES (:acc, :reg) RETURNING id"),
        {"acc": "123456789012", "reg": "us-west-2"},
    ).scalar_one()

    conn.execute(
        text(
            "INSERT INTO resources (scan_id, resource_type, resource_id, name, config, monthly_cost_usd) "
            "VALUES (:sid, :rtype, :rid, :name, CAST(:config AS JSONB), :cost)"
        ),
        {
            "sid": scan_id,
            "rtype": "s3_bucket",
            "rid": "backup-bucket",
            "name": "backup-bucket",
            "config": json.dumps({"versioning": True, "public": False}),
            "cost": 5.25,
        },
    )

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT scan_id, name, resource_type FROM resources ORDER BY id")
    ).all()
    for row in rows:
        print(row)