import asyncio
import aiosqlite
import requests
from dotenv import load_dotenv

from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# -------------------
# 1. Define State & Sync Tools
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

search_tool = DuckDuckGoSearchRun(region="us-en")

# Note: Ideally, use 'httpx' or 'aiohttp' here for true async, 
# but 'requests' works fine because LangGraph handles it safely.
@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    r = requests.get(url)
    return r.json()

# -------------------
# 2. The Main Async Application
# -------------------
async def main():
    print("--- Starting Chatbot Setup ---")

    # A. Setup Database Connection (Async)
    # We use 'async with' so it auto-closes the connection when done
    async with aiosqlite.connect("chatbot.db") as conn:
        checkpointer = AsyncSqliteSaver(conn)

        # B. Setup MCP Client & Tools (Async)
        client = MultiServerMCPClient(
            {
                "arith": {
                    "transport": "stdio",
                    "command": "python3",
                    "args": ["/Users/nitish/Desktop/mcp-math-server/main.py"],
                },
                "expense": {
                    "transport": "streamable_http", 
                    "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
                }
            }
        )

        try:
            # We can directly await this now! No threads needed.
            print("Fetching MCP tools...")
            mcp_tools = await client.get_tools()
            print(f"Loaded {len(mcp_tools)} MCP tools.")
        except Exception as e:
            print(f"Failed to load MCP tools: {e}")
            mcp_tools = []

        # C. Bind Tools to LLM
        all_tools = [search_tool, get_stock_price, *mcp_tools]
        llm = ChatOpenAI()
        
        if all_tools:
            llm_with_tools = llm.bind_tools(all_tools)
        else:
            llm_with_tools = llm

        # D. Define Nodes
        async def chat_node(state: ChatState):
            messages = state["messages"]
            # We use ainvoke for async execution
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}

        # E. Build Graph
        graph_builder = StateGraph(ChatState)
        graph_builder.add_node("chat_node", chat_node)
        graph_builder.add_edge(START, "chat_node")

        if all_tools:
            tool_node = ToolNode(all_tools)
            graph_builder.add_node("tools", tool_node)
            graph_builder.add_conditional_edges("chat_node", tools_condition)
            graph_builder.add_edge("tools", "chat_node")
        else:
            graph_builder.add_edge("chat_node", END)

        # F. Compile with Checkpointer
        chatbot = graph_builder.compile(checkpointer=checkpointer)

        # -------------------
        # 3. Run the Bot
        # -------------------
        print("--- Running Bot ---")
        
        # Configure the thread ID for memory
        config = {"configurable": {"thread_id": "thread-1"}}
        
        # We can now use 'async for' to stream events naturally
        user_input = "What is the stock price of Apple?"
        input_message = HumanMessage(content=user_input)

        async for event in chatbot.astream({"messages": [input_message]}, config):
            # Print the final update of each node
            for node, values in event.items():
                print(f"Update from node: {node}")
                # print(values) # Uncomment to see full state

        print("--- Done ---")
        
        # Optional: Inspect checkpoints
        # async for cp in checkpointer.alist(config):
        #    print(cp)

# -------------------
# 4. Entry Point
# -------------------
if __name__ == "__main__":
    # This is the standard way to run an async script
    asyncio.run(main())