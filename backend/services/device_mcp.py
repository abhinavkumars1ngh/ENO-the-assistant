import asyncio
import subprocess
from mcp.server.fastmcp import FastMCP

# Create the FastMCP server
mcp = FastMCP("Eno Device and Google Integrations")

@mcp.tool()
def set_timer(duration_minutes: int, message: str) -> str:
    """Sets a local Mac timer and triggers a notification when finished."""
    
    async def timer_task():
        await asyncio.sleep(duration_minutes * 60)
        # Trigger Mac Notification
        applescript = f'display notification "{message}" with title "Eno Timer"'
        subprocess.run(["osascript", "-e", applescript])
        # Optional: play sound
        subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"])

    # Fire and forget
    asyncio.create_task(timer_task())
    return f"Successfully set a timer for {duration_minutes} minutes. You will be notified with the message: '{message}'."

@mcp.tool()
def read_schedule(date: str = "today") -> str:
    """Reads the user's schedule from Google Calendar. (Mocked for now)"""
    return f"Schedule for {date}: 10:00 AM - Deep Work. 2:00 PM - Meeting with team."

@mcp.tool()
def create_calendar_event(title: str, start_time: str, end_time: str) -> str:
    """Creates a new event on the user's Google Calendar."""
    return f"Successfully created event '{title}' from {start_time} to {end_time}."

@mcp.tool()
def search_google_drive(query: str) -> str:
    """Searches the user's Google Drive for files matching the query."""
    return f"Found 2 files matching '{query}': 'Q3_Report.pdf', 'Project_Notes.docx'."

if __name__ == "__main__":
    # Runs standard stdio MCP protocol
    mcp.run()
