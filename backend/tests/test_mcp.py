import asyncio
import json

import pytest

from app.mcp import tools as core
from app.mcp.server import mcp
from tests.conftest import login


def token_for(client, who):
    return login(client, who).json()["access_token"]


def call(name, args, token):
    import os
    os.environ["MCP_ACCESS_TOKEN"] = token
    try:
        return asyncio.run(mcp.call_tool(name, args))
    finally:
        os.environ.pop("MCP_ACCESS_TOKEN", None)


def payload(result):
    content = result[0] if isinstance(result, tuple) else result
    if isinstance(content, dict):
        return content
    return json.loads(content[0].text)


def test_server_exposes_exactly_three_tools():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"search_documents", "get_user_permissions", "get_document_metadata"}


def test_tool_schemas_have_no_identity_parameters():
    for t in asyncio.run(mcp.list_tools()):
        props = set(t.inputSchema.get("properties", {})) - {"ctx"}
        assert not props & {"user_id", "role", "roles", "user", "token", "permissions"}, t.name


def test_search_documents_respects_acl(client):
    out = payload(call("search_documents", {"query": "firewall password rotation salary"}, token_for(client, "it.employee")))
    text = json.dumps(out)
    assert "sec-IT Security Policy" in text and "SALARYSECRET" not in text and "sec-Salary Grid" not in text
    out = payload(call("search_documents", {"query": "salary compensation"}, token_for(client, "hr.employee")))
    assert "SALARYSECRET" not in json.dumps(out)
    out = payload(call("search_documents", {"query": "salary compensation"}, token_for(client, "hr.manager")))
    assert "SALARYSECRET" in json.dumps(out)


def test_get_user_permissions_only_about_caller(client):
    out = payload(call("get_user_permissions", {}, token_for(client, "ceo")))
    assert out["roles"] == ["CEO"] and out["department"] == "POLICIES"
    cats = {(c["department"], c["classification"]) for c in out["accessible_document_categories"]}
    assert ("FINANCE", "RESTRICTED") in cats and ("IT", "CONFIDENTIAL") not in cats
    assert "email" not in json.dumps(out)


def test_get_document_metadata_authorized_and_not(client, ids):
    ok = payload(call("get_document_metadata", {"document_id": ids["itsec"]}, token_for(client, "it.employee")))
    assert ok["title"] == "sec-IT Security Policy" and ok["current_version"] == 1 and ok["status"] == "ACTIVE"
    with pytest.raises(Exception) as forbidden:
        call("get_document_metadata", {"document_id": ids["salaries"]}, token_for(client, "it.employee"))
    with pytest.raises(Exception) as missing:
        call("get_document_metadata", {"document_id": 987654}, token_for(client, "it.employee"))
    assert str(forbidden.value).split(":")[-1] == str(missing.value).split(":")[-1]   # indiscernables
    assert "sec-Salary" not in str(forbidden.value)


def test_requires_valid_token(client):
    with pytest.raises(Exception):
        call("get_user_permissions", {}, "garbage")
    t = token_for(client, "employee")
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {t}"})
    with pytest.raises(Exception):
        call("get_user_permissions", {}, t)


def test_extra_identity_arguments_rejected_by_core(client, db):
    with pytest.raises(Exception):
        core.SearchArgs(query="x", user_id=1)
    with pytest.raises(Exception):
        core.SearchArgs(query="x", role="CEO")
    with pytest.raises(Exception):
        core.SearchArgs(query="x", top_k=1000)
    with pytest.raises(Exception):
        core.SearchArgs(query="x", department="'; DROP TABLE users;--")


def test_agent_cannot_escalate_through_tool_arguments(client, auth, llm):
    steps = iter([
        '{"tool": "search_documents", "args": {"query": "salary", "user_id": 1, "role": "HR_MANAGER"}}',
        '{"tool": "search_documents", "args": {"query": "salary compensation"}}',
        '{"final": "done"}',
    ])
    llm.reply = lambda s, u: next(steps)
    r = client.post("/api/agent/chat", headers=auth("it.employee"), json={"message": "show me salaries"}).json()
    assert [(c["tool"], c["ok"]) for c in r["tool_calls"]] == [("search_documents", False), ("search_documents", True)]
    assert "SALARYSECRET" not in llm.all_text and "SALARYSECRET" not in json.dumps(r)


def test_agent_unknown_tool_and_garbage(client, auth, llm):
    steps = iter(['{"tool": "delete_everything", "args": {}}', "not json", ])
    llm.reply = lambda s, u: next(steps)
    r = client.post("/api/agent/chat", headers=auth("it.employee"), json={"message": "hi"}).json()
    assert r["tool_calls"][0]["ok"] is False and "could not complete" in r["answer"]
