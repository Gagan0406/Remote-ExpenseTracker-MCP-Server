import random 
from fastmcp import FastMCP

mcp = FastMCP(name = "Demo Server")
@mcp.tool
def roll_dice(n_dice: int):
    """Rolls a dice n times and returns the result"""
    return [random.randint(1, 6) for _ in range(n_dice)]

@mcp.tool
def add(a: int, b: int):
    """Adds two numbers and returns the result"""
    return a + b

if __name__ == "__main__":
    mcp.run()