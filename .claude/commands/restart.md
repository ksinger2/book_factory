# /restart - Restart BookFactory Docker Container

Rebuild and restart the BookFactory Docker container.

## Instructions

Run the following command from the project root:

```bash
docker compose up -d --build bookfactory
```

This will:
1. Rebuild the Docker image with the latest code changes
2. Restart the `bookfactory` container on port 5555
3. Leave the Cloudflare tunnel container untouched

After the command completes, confirm the container is running:

```bash
docker compose ps bookfactory
```

Report the result to the user (running/failed, port, uptime).
