Create plain-text secret files in this folder before starting `docker compose -f docker-compose.prod.yml up -d`.

Required files:

- `mysql_password.txt`
- `mysql_root_password.txt`
- `app_secret_key.txt`
- `msg91_auth_key.txt` if using MSG91
- `gupshup_api_key.txt` if using Gupshup WhatsApp
- `gupshup_sms_password.txt` if using Gupshup SMS
- `provider_webhook_token.txt` if you want signed delivery callback endpoints

Keep the real values out of git. The repository `.gitignore` already excludes `deploy/secrets/*.txt`.
