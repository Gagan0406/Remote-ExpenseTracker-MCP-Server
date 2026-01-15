from fastmcp import FastMCP

mcp = FastMCP.as_proxy(
    "https://magnetic-harlequin-ape.fastmcp.app/mcp",
    name = "ExpenseTrackerProxy"
)

if __name__ == "__main__":
    mcp.run()