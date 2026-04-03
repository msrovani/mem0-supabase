"""
Postman Collection Export — Mem0 API

Import this file into Postman to get a complete API testing suite.

Usage:
    1. Open Postman
    2. Import → File → select this JSON
    3. Set environment variables:
       - base_url: http://localhost:8000
       - jwt_token: your-jwt-token
"""

import json

collection = {
    "info": {
        "name": "Mem0 API",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "description": "Complete API testing suite for Mem0-Supabase"
    },
    "auth": {
        "type": "bearer",
        "bearer": [{"key": "token", "value": "{{jwt_token}}", "type": "string"}]
    },
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000", "type": "string"},
        {"key": "jwt_token", "value": "", "type": "string"},
        {"key": "user_id", "value": "postman_test_user", "type": "string"},
        {"key": "memory_id", "value": "", "type": "string"}
    ],
    "item": [
        {
            "name": "Health",
            "request": {
                "method": "GET",
                "header": [],
                "url": {"raw": "{{base_url}}/health", "host": ["{{base_url}}"], "path": ["health"]},
                "description": "Check API health with live DB/LLM connectivity"
            }
        },
        {
            "name": "Create Memory",
            "event": [
                {
                    "listen": "test",
                    "script": {
                        "exec": [
                            "var jsonData = pm.response.json();",
                            "if (jsonData.results && jsonData.results.length > 0) {",
                            "    pm.environment.set('memory_id', jsonData.results[0].id);",
                            "}"
                        ],
                        "type": "text/javascript"
                    }
                }
            ],
            "request": {
                "method": "POST",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({
                        "messages": [{"role": "user", "content": "User likes pizza and lives in New York"}],
                        "user_id": "{{user_id}}",
                        "idempotency_key": "req_{{{{$guid}}}}"
                    })
                },
                "url": {"raw": "{{base_url}}/memories", "host": ["{{base_url}}"], "path": ["memories"]}
            }
        },
        {
            "name": "Search Memories",
            "request": {
                "method": "POST",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({"query": "food preferences", "user_id": "{{user_id}}"})
                },
                "url": {"raw": "{{base_url}}/search", "host": ["{{base_url}}"], "path": ["search"]}
            }
        },
        {
            "name": "Get All Memories",
            "request": {
                "method": "GET",
                "header": [],
                "url": {
                    "raw": "{{base_url}}/memories?user_id={{user_id}}&limit=10",
                    "host": ["{{base_url}}"],
                    "path": ["memories"],
                    "query": [
                        {"key": "user_id", "value": "{{user_id}}"},
                        {"key": "limit", "value": "10"},
                        {"key": "cursor", "value": ""}
                    ]
                }
            }
        },
        {
            "name": "Get Single Memory",
            "request": {
                "method": "GET",
                "header": [],
                "url": {"raw": "{{base_url}}/memories/{{memory_id}}", "host": ["{{base_url}}"], "path": ["memories", "{{memory_id}}"]}
            }
        },
        {
            "name": "Update Memory",
            "request": {
                "method": "PUT",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({"data": "User loves pizza and lives in Brooklyn"})
                },
                "url": {"raw": "{{base_url}}/memories/{{memory_id}}", "host": ["{{base_url}}"], "path": ["memories", "{{memory_id}}"]}
            }
        },
        {
            "name": "Get Memory History",
            "request": {
                "method": "GET",
                "header": [],
                "url": {"raw": "{{base_url}}/memories/{{memory_id}}/history", "host": ["{{base_url}}"], "path": ["memories", "{{memory_id}}", "history"]}
            }
        },
        {
            "name": "Bulk Create Memories",
            "request": {
                "method": "POST",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({
                        "items": [
                            {"messages": [{"role": "user", "content": "User likes coding"}], "user_id": "{{user_id}}"},
                            {"messages": [{"role": "user", "content": "User works at a tech company"}], "user_id": "{{user_id}}"},
                            {"messages": [{"role": "user", "content": "User enjoys open source"}], "user_id": "{{user_id}}"}
                        ]
                    })
                },
                "url": {"raw": "{{base_url}}/memories/bulk", "host": ["{{base_url}}"], "path": ["memories", "bulk"]}
            }
        },
        {
            "name": "Delete Memory",
            "request": {
                "method": "DELETE",
                "header": [],
                "url": {"raw": "{{base_url}}/memories/{{memory_id}}", "host": ["{{base_url}}"], "path": ["memories", "{{memory_id}}"]}
            }
        },
        {
            "name": "Delete All Memories",
            "request": {
                "method": "DELETE",
                "header": [],
                "url": {"raw": "{{base_url}}/memories?user_id={{user_id}}", "host": ["{{base_url}}"], "path": ["memories"], "query": [{"key": "user_id", "value": "{{user_id}}"}]}
            }
        },
        {
            "name": "Reset All Memories",
            "request": {
                "method": "POST",
                "header": [],
                "url": {"raw": "{{base_url}}/reset", "host": ["{{base_url}}"], "path": ["reset"]}
            }
        }
    ]
}

if __name__ == "__main__":
    with open("tests/mem0_api.postman_collection.json", "w") as f:
        json.dump(collection, f, indent=2)
    print("Postman collection exported to tests/mem0_api.postman_collection.json")
