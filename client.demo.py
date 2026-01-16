import os
import json
import asyncio
import streamlit as st
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

SERVERS = { 
    "expense": {
        "transport": "streamable_http",
        "url": "https://magnetic-harlequin-ape.fastmcp.app/mcp"
    },
    # "manim-server": {
    #     "transport": "stdio",
    #     "command": "C:\\Users\\gagan\\OneDrive\\Desktop\\Projects\\Expense Tracker MCP Server\\.venv\\Scripts\\python.exe",
    #     "args": [
    #         "C:\\Users\\gagan\\OneDrive\\Desktop\\Projects\\Expense Tracker MCP Server\\manim-mcp-server\\src\\manim_server.py"
    #     ],
    #     "env": {
    #         "MANIM_EXECUTABLE": "C:\\Users\\gagan\\OneDrive\\Desktop\\Projects\\Expense Tracker MCP Server\\.venv\\Scripts\\manim.exe"
    #     }
    # }
}

SYSTEM_PROMPT = (
    "You have access to tools. When you choose to call a tool, do not narrate status updates. "
    "After tools run, return only a concise final answer."
)

st.set_page_config(page_title="MCP Chat", page_icon="🧰", layout="centered")
st.title("🧰 MCP Chat")

load_dotenv()

if "initialized" not in st.session_state:
    st.session_state.llm = ChatOpenAI(
        model="lmstudio-community/Qwen2.5-7B-Instruct-1M-GGUF", 
        openai_api_key="none",
        # base_url="http://host.docker.internal:1234/v1" for docker
        base_url = "http://127.0.0.1:1234/v1"
    )

    st.session_state.client = MultiServerMCPClient(SERVERS)
    tools = asyncio.run(st.session_state.client.get_tools())
    st.session_state.tools = tools
    st.session_state.tool_by_name = {t.name: t for t in tools}

    st.session_state.llm_with_tools = st.session_state.llm.bind_tools(tools)

    st.session_state.history = [SystemMessage(content=SYSTEM_PROMPT)]
    st.session_state.initialized = True

for msg in st.session_state.history:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        if getattr(msg, "tool_calls", None):
            continue
        with st.chat_message("assistant"):
            st.markdown(msg.content)

user_text = st.chat_input("Type a message…")
if user_text:
    with st.chat_message("user"):
        st.markdown(user_text)
    st.session_state.history.append(HumanMessage(content=user_text))

    first = asyncio.run(st.session_state.llm_with_tools.ainvoke(st.session_state.history))
    tool_calls = getattr(first, "tool_calls", None)

    if not tool_calls:
        with st.chat_message("assistant"):
            st.markdown(first.content or "")
        st.session_state.history.append(first)
    else:
        st.session_state.history.append(first)

        tool_msgs = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            tool = st.session_state.tool_by_name[name]
            res = asyncio.run(tool.ainvoke(args))
            tool_msgs.append(ToolMessage(tool_call_id=tc["id"], content=json.dumps(res)))

        st.session_state.history.extend(tool_msgs)

        final = asyncio.run(st.session_state.llm.ainvoke(st.session_state.history))
        with st.chat_message("assistant"):
            st.markdown(final.content or "")
        st.session_state.history.append(AIMessage(content=final.content or ""))