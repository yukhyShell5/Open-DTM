import subprocess
import json

def test_task_added():
    subprocess.run([
        "curl", "-s",
        "-X", "POST",
        "http://localhost:8000/submit_task?command=echo%20hello"
    ])

    tasks = json.loads(subprocess.run(
        ["curl", "-s", "http://localhost:8000/tasks"],
        capture_output=True, text=True
    ).stdout)

    assert len(tasks) > 0
