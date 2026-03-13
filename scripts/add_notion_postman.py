"""One-shot script: add Notion connector requests to the Postman collection."""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
COLLECTION_PATH = os.path.join(ROOT, "docs", "postman", "PersonalAPI.postman_collection.json")

with open(COLLECTION_PATH, "r", encoding="utf-8") as f:
    col = json.load(f)

# -- Variables ---------------------------------------------------------------
existing_var_keys = {v["key"] for v in col.get("variable", [])}
new_vars = [
    {"key": "notionToken", "value": "", "type": "string",
     "description": "Notion internal integration token (starts with ntn_ or secret_)"},
    {"key": "notionAuthUrl", "value": "", "type": "string",
     "description": "Notion OAuth URL from /notion/connect"},
    {"key": "notionAuthCode", "value": "", "type": "string",
     "description": "Code from Notion OAuth callback"},
    {"key": "notionAuthState", "value": "", "type": "string",
     "description": "State from Notion OAuth callback"},
]
for v in new_vars:
    if v["key"] not in existing_var_keys:
        col["variable"].append(v)

# -- Request definitions ------------------------------------------------------
notion_requests = [
    {
        "name": "Notion - Quick Connect (Internal Token)",
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('Status 200', function() { pm.response.to.have.status(200); });",
                        "var body = pm.response.json();",
                        "pm.test('Connected', function() { pm.expect(body.status).to.eql('connected'); });",
                        "console.log('Notion workspace: ' + body.workspace);",
                    ],
                },
            }
        ],
        "request": {
            "method": "POST",
            "header": [
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Authorization", "value": "Bearer {{accessToken}}"},
            ],
            "body": {
                "mode": "raw",
                "raw": '{\n  "access_token": "{{notionToken}}"\n}',
                "options": {"raw": {"language": "json"}},
            },
            "url": {
                "raw": "{{baseUrl}}/{{apiPrefix}}/connectors/notion/token",
                "host": ["{{baseUrl}}"],
                "path": ["{{apiPrefix}}", "connectors", "notion", "token"],
            },
            "description": (
                "Register a Notion internal integration token directly (no OAuth needed). "
                "Get your token from https://www.notion.so/my-integrations"
            ),
        },
    },
    {
        "name": "Notion - Get Connect URL (OAuth)",
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('Status 200', function() { pm.response.to.have.status(200); });",
                        "var body = pm.response.json();",
                        "if (body.url) { pm.collectionVariables.set('notionAuthUrl', body.url); }",
                        "console.log('Notion OAuth URL: ' + (body.url || 'not returned'));",
                    ],
                },
            }
        ],
        "request": {
            "method": "GET",
            "header": [{"key": "Authorization", "value": "Bearer {{accessToken}}"}],
            "url": {
                "raw": "{{baseUrl}}/{{apiPrefix}}/connectors/notion/connect",
                "host": ["{{baseUrl}}"],
                "path": ["{{apiPrefix}}", "connectors", "notion", "connect"],
            },
            "description": "Get OAuth authorisation URL. Requires NOTION_CLIENT_ID + NOTION_CLIENT_SECRET in .env",
        },
    },
    {
        "name": "Notion - Callback (Manual Code Exchange)",
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "if (!pm.collectionVariables.get('notionAuthCode')) { throw new Error('Set notionAuthCode first'); }",
                    ],
                },
            }
        ],
        "request": {
            "method": "GET",
            "header": [],
            "url": {
                "raw": "{{baseUrl}}/{{apiPrefix}}/connectors/notion/callback?code={{notionAuthCode}}&state={{notionAuthState}}",
                "host": ["{{baseUrl}}"],
                "path": ["{{apiPrefix}}", "connectors", "notion", "callback"],
                "query": [
                    {"key": "code", "value": "{{notionAuthCode}}"},
                    {"key": "state", "value": "{{notionAuthState}}"},
                ],
            },
            "description": "Exchange Notion OAuth code. Paste code and state from browser redirect into collection variables.",
        },
    },
    {
        "name": "Notion - Get Connector",
        "request": {
            "method": "GET",
            "header": [{"key": "Authorization", "value": "Bearer {{accessToken}}"}],
            "url": {
                "raw": "{{baseUrl}}/{{apiPrefix}}/connectors/notion",
                "host": ["{{baseUrl}}"],
                "path": ["{{apiPrefix}}", "connectors", "notion"],
            },
        },
    },
    {
        "name": "Notion - Trigger Sync",
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('Accepted or OK', function() { pm.expect(pm.response.code).to.be.oneOf([200, 202]); });",
                        "var body = pm.response.json();",
                        "console.log('Sync result: ' + JSON.stringify(body));",
                    ],
                },
            }
        ],
        "request": {
            "method": "POST",
            "header": [{"key": "Authorization", "value": "Bearer {{accessToken}}"}],
            "url": {
                "raw": "{{baseUrl}}/{{apiPrefix}}/connectors/notion/sync",
                "host": ["{{baseUrl}}"],
                "path": ["{{apiPrefix}}", "connectors", "notion", "sync"],
            },
            "description": "Trigger incremental Notion workspace sync (pages + database rows).",
        },
    },
]

# -- Insert into Connectors folder -------------------------------------------
connectors_folder = next(f for f in col["item"] if f["name"] == "Connectors")
existing_names = {i["name"] for i in connectors_folder["item"]}

insert_after = "Spotify - Trigger Sync"
insert_idx = next(
    (idx + 1 for idx, item in enumerate(connectors_folder["item"]) if item["name"] == insert_after),
    len(connectors_folder["item"]),
)

for req in reversed(notion_requests):
    if req["name"] not in existing_names:
        connectors_folder["item"].insert(insert_idx, req)

with open(COLLECTION_PATH, "w", encoding="utf-8") as f:
    json.dump(col, f, indent=2)

print("Updated. Connectors folder now contains:")
for item in connectors_folder["item"]:
    print(" -", item["name"])
