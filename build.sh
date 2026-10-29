#!/usr/bin/env bash
# Runs on every deploy on Render (see the "Build Command" setting).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Render's free plan has no shell, so the owner account is created here from
# environment variables. It is skipped if the account already exists.
if [ -n "$OWNER_USERNAME" ] && [ -n "$OWNER_PASSWORD" ] && [ -n "$OWNER_PHONE" ]; then
  python manage.py create_owner --if-missing --name "${OWNER_NAME:-Admin}" \
      --username "$OWNER_USERNAME" --phone "$OWNER_PHONE" --password "$OWNER_PASSWORD"
fi
