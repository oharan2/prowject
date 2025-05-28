import os
from typing import Any, Optional
import json
import re

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-server")

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.ci.openshift.org")
CONSOLE_URL = os.environ.get("CONSOLE_URL", "https://console.build02.ci.openshift.org")

async def make_request(
    url: str, method: str = "GET", data: dict[str, Any] = None, headers: dict[str, str] = None
) -> dict[str, Any] | None:
    """Make an HTTP request with optional authentication."""
    default_headers = {"Accept": "application/json"}
    if headers:
        default_headers.update(headers)
    
    api_key = os.environ.get("API_KEY")
    if api_key:
        default_headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.request(method, url, headers=default_headers, params=data)
        else:
            response = await client.request(method, url, headers=default_headers, json=data)
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def get_job_namespace(pr_url: str) -> dict:
    """Get the namespace information for a running CI job from a PR URL.
    
    Args:
        pr_url: URL to the pull request (e.g., https://github.com/org/repo/pull/123)
    
    Returns:
        Dictionary containing namespace and console URLs
    """
    # Extract PR info from URL
    match = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError("Invalid PR URL format")
    
    org, repo, pr_num = match.groups()
    
    # Get PR jobs info
    url = f"{API_BASE_URL}/prow/prowjobs"
    params = {
        "org": org,
        "repo": repo,
        "pull": pr_num,
        "state": "running"
    }
    
    response = await make_request(url, data=params)
    if not response or not response.get("items"):
        return {"error": "No running jobs found for this PR"}
    
    namespaces = []
    for job in response["items"]:
        namespace = job.get("metadata", {}).get("namespace")
        if namespace and namespace.startswith("ci-op-"):
            console_url = f"{CONSOLE_URL}/k8s/cluster/projects/{namespace}"
            namespaces.append({
                "namespace": namespace,
                "console_url": console_url,
                "job_name": job.get("spec", {}).get("job"),
                "job_type": job.get("spec", {}).get("type")
            })
    
    return {"namespaces": namespaces}

@mcp.tool()
async def get_job_logs(namespace: str, container: Optional[str] = None) -> dict:
    """Get logs from pods in a CI job namespace.
    
    Args:
        namespace: The CI job namespace (e.g., ci-op-1234abcd)
        container: Optional container name to filter logs
    
    Returns:
        Dictionary containing pod logs
    """
    url = f"{API_BASE_URL}/api/v1/namespaces/{namespace}/pods"
    response = await make_request(url)
    
    logs = {}
    for pod in response.get("items", []):
        pod_name = pod["metadata"]["name"]
        
        # Get logs for each container
        for container_status in pod["status"].get("containerStatuses", []):
            container_name = container_status["name"]
            if container and container != container_name:
                continue
                
            log_url = f"{API_BASE_URL}/api/v1/namespaces/{namespace}/pods/{pod_name}/log"
            if container:
                log_url += f"?container={container}"
            
            try:
                log_response = await make_request(log_url)
                logs[f"{pod_name}/{container_name}"] = log_response
            except Exception as e:
                logs[f"{pod_name}/{container_name}"] = f"Error fetching logs: {str(e)}"
    
    return {"logs": logs}

@mcp.tool()
async def get_test_cluster_info(namespace: str) -> dict:
    """Get information about the ephemeral test cluster for a CI job.
    
    Args:
        namespace: The CI job namespace (e.g., ci-op-1234abcd)
    
    Returns:
        Dictionary containing cluster information
    """
    # Get cluster info from configmap
    url = f"{API_BASE_URL}/api/v1/namespaces/{namespace}/configmaps"
    response = await make_request(url)
    
    cluster_info = {}
    for configmap in response.get("items", []):
        if "cluster" in configmap["metadata"]["name"].lower():
            cluster_info.update(configmap.get("data", {}))
    
    return {"cluster_info": cluster_info}

if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
