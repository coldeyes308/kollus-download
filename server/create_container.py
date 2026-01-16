import docker
import time
import random
import string
import os
import sys

amount = int(sys.argv[1]) if sys.argv[1] else 1
startup_timeout_seconds = int(os.getenv("KOLLUS_STARTUP_TIMEOUT_SECONDS", "180"))
startup_poll_seconds = float(os.getenv("KOLLUS_STARTUP_POLL_SECONDS", "0.5"))
startup_missing_process_threshold = int(
    os.getenv("KOLLUS_STARTUP_MISSING_PROCESS_THRESHOLD", "6")
)
containers = []

for i in range(amount):
    port = str(random.randint(10000, 60000))

    name = ''.join(random.choices(string.ascii_letters + string.digits, k=15))

    client = docker.from_env()
    container = client.containers.run(
        "scottyhardy/docker-wine",
        name=f"kollus_download_{''.join(random.choices(string.ascii_letters + string.digits, k=15))}",
        detach=True, 
        ports={f"80/tcp": port},
        network="kollus-client_net",
        entrypoint="",
        remove=True,
        volumes={
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "mount"): {
                'bind': '/mount', 
                'mode': 'ro'
            }
        },
        command=
        r"""
            /bin/sh -c " \
                wget http://mitm.it/cert/pem && \
                mv pem /usr/local/share/ca-certificates/mitmproxy.crt && \
                update-ca-certificates && \
                xvfb-run wine /mount/KollusPlayer3/KollusAgent.exe & \
                /mount/http-to-https-proxy/proxy \
            "
        """
    )

    print(f"{container.name}")
    
    containers.append(container)

for container in containers:
    start_time = time.time()
    missing_process_count = 0
    while True:
        if "Connected to root\\WMI WMI namespace".encode("utf-8") in container.logs():
            print(f"Container {container.name} finished startup")
            break

        process_result = container.exec_run("pgrep -f KollusAgent.exe")
        if process_result.exit_code != 0:
            missing_process_count += 1
        else:
            missing_process_count = 0

        if missing_process_count >= startup_missing_process_threshold:
            print("KollusAgent.exe is not running inside the container.")
            print(
                "Container logs:",
                container.logs().decode("utf-8", errors="replace"),
                sep="\n",
            )
            raise SystemExit(1)

        if time.time() - start_time > startup_timeout_seconds:
            print(
                "Startup timed out while waiting for WMI. Container logs:",
                container.logs().decode("utf-8", errors="replace"),
                sep="\n",
            )
            print(
                f"Container {container.name} did not report WMI readiness within "
                f"{startup_timeout_seconds} seconds."
            )
            raise SystemExit(1)

        time.sleep(startup_poll_seconds)
