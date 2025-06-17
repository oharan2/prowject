import os
from typing import Any
from dateutil.parser import parse as parse_date

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-server")

PROW_URL = "https://prow.ci.openshift.org"
GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

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
            "build_id": status.get("build_id")
        }
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}


@mcp.tool()
async def get_job_logs(job_id: str):
    """Get the logs for a specific Prow job ID.
    
    Args:
        job_id: The ID of the job to get logs for
        
    Returns:
        Dictionary containing the job logs or error information
    """
    url = f"{PROW_URL}/prowjobs.js"
    try:
        response = await make_request(url)
        if not response:
            return {"error": "No response from Prow API"}
            
        prowjobs = response.get("items", [])

        # Find the job with matching ID
        matching_job = next(
            (job for job in prowjobs if job["metadata"]["name"] == job_id),
            None
        )

        if not matching_job:
            return {"error": f"No job found with ID: {job_id}"}

        # Get the build logs URL
        status = matching_job.get("status", {})
        build_id = status.get("build_id")
        job_name = matching_job.get("spec", {}).get("job")
        
        if not build_id or not job_name:
            return {"error": "Could not find build ID or job name"}

        return await get_build_logs(job_name, build_id)
            
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}


@mcp.tool()
async def get_build_logs(job_name: str, build_id: str):
    """Get the logs for a specific build ID and job name.
    
    Args:
        job_name: The name of the job
        build_id: The build ID to get logs for
        
    Returns:
        Dictionary containing the job logs or error information
    """
    try:
        # Construct the artifacts URL
        artifacts_url = f"{GCS_URL}/{job_name}/{build_id}/artifacts"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GCS_URL}/{job_name}/{build_id}/build-log.txt")
            response.raise_for_status()
            logs = response.text
            return {
                "build_id": build_id,
                "job_name": job_name,
                "logs": logs,
                "artifacts_url": artifacts_url
            }
    except Exception as e:
        return {
            "error": f"Failed to fetch logs: {str(e)}",
            "artifacts_url": artifacts_url if 'artifacts_url' in locals() else None
        }


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
