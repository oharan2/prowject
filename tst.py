import requests
from dateutil.parser import parse as parse_date

prow_url = "https://prow.ci.openshift.org"


def get_latest_job_run(prow_url, job_name):
    url = f"{prow_url}/prowjobs.js"
    response = requests.get(url)
    response.raise_for_status()

    prowjobs = response.json().get("items", [])

    # Filter by job name
    matching_jobs = [
        job for job in prowjobs
        if job.get("spec", {}).get("job") == job_name and "startTime" in job.get("status", {})
    ]

    if not matching_jobs:
        print(f"No matching job found for: {job_name}")
        return None

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


