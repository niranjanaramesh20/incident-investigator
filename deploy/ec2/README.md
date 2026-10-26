# Deploy on Ubuntu EC2

These templates match the app running at `/opt/incident-investigator` on an
Ubuntu EC2 instance with PostgreSQL and Nginx installed. The backend listens on
localhost port 8000; Nginx serves the built React app and proxies API calls.

## Configure the server

1. Copy the project to `/opt/incident-investigator` and build the frontend:

   ```bash
   cd /opt/incident-investigator/frontend
   npm ci
   npm run build
   ```

2. Create `/opt/incident-investigator/.env` from the root `.env.example`. Set
   the production PostgreSQL URL, `OPENAI_API_KEY`, and a random
   `SESSION_SECRET`. For the public demo, set `ALLOW_PUBLIC_ACCESS=true` and
   `TRUST_PROXY_HEADERS=true` because Nginx overwrites `X-Real-IP`. Keep this
   file private and set its permissions to `600`.

3. Create the backend virtual environment and install dependencies:

   ```bash
   cd /opt/incident-investigator
   python3 -m venv .venv
   .venv/bin/pip install --no-cache-dir -r backend/requirements.txt
   cd backend
   ../.venv/bin/alembic upgrade head
   ```

4. Install and start the service and Nginx site:

   ```bash
   sudo install -m 644 /opt/incident-investigator/deploy/ec2/incident-investigator.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now incident-investigator
   sudo install -m 644 /opt/incident-investigator/deploy/ec2/nginx-site.conf /etc/nginx/sites-available/default
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. Allow inbound TCP port 80 in the EC2 security group. Keep PostgreSQL bound to
   localhost and restrict SSH inbound access to trusted addresses.

The Nginx template serves HTTP. Configure TLS for a domain before using the
public app with sensitive evidence. Public evidence and investigations share
the same database and Chroma index. The **Load sample data** button adds the
bundled demo records on demand; indexing and investigations can incur OpenAI
API charges.

PostgreSQL and Chroma data are stored on the instance volume. Back them up
before replacing the instance or its EBS volume.
