import os
from typing import Any
from dateutil.parser import parse as parse_date

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-server")

PROW_URL = "https://prow.ci.openshift.org"

async def make_request(
    url: str, method: str = "GET", data: dict[str, Any] = None
) -> dict[str, Any] | None:
    api_key = os.environ.get("API_KEY")
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
    else:
        headers = {}

    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.request(method, url, headers=headers, params=data)
        else:
            response = await client.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()



@mcp.tool()
async def get_latest_job_run(job_name: str):
    """Get the latest job run information from Prow for a specific job name.
    
    Args:
        job_name: The name of the Prow job to query
        
    Returns:
        Dictionary containing job information including ID, state, start time, completion time, and URL
    """
    url = f"{PROW_URL}/prowjobs.js"
    try:
        response = await make_request(url)
        if not response:
            return {"error": "No response from Prow API"}
            
        prowjobs = response.get("items", [])

        # Filter by job name
        matching_jobs = [
            job for job in prowjobs
            if job.get("spec", {}).get("job") == job_name and "startTime" in job.get("status", {})
        ]

        if not matching_jobs:
            return {"error": f"No matching job found for: {job_name}"}

        # Sort by startTime descending
        matching_jobs.sort(
            key=lambda job: parse_date(job["status"]["startTime"]),
            reverse=True
        )

        latest = matching_jobs[0]
        status = latest.get("status", {})

        return {
            "job_id": latest["metadata"]["name"],
            "state": status.get("state"),
            "start": status.get("startTime"),
            "completion": status.get("completionTime"),
            "url": status.get("url"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
