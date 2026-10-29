# StenoMaster

Stenography dictation practice site. Django 6.1 + SQLite + plain HTML/CSS/JS.

## First-time setup (bash on Ubuntu)

```bash
cd stenomaster
python3 -m venv .Stenoenv        # Ubuntu may need: sudo apt install python3-venv
source .Stenoenv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_owner        # asks for name, username, phone, password
python manage.py runserver
```

Open http://127.0.0.1:8000/ . Log in as the owner with the phone number you typed (or the username)
and you land on the **Admin** page: Upload, Students (with passwords), latest submissions.

Students register themselves on the Register page (name, username, phone, password - no email).

## Where to change things

| What | File |
|---|---|
| Admin phone number + the "contact if you forgot..." sentence in the footer | `steno_project/settings.py` (`ADMIN_CONTACT_PHONE`, `ADMIN_CONTACT_MESSAGE`) |
| Reading time (5 min), typing time (50 min), speed slider range (60-120 WPM) | `steno_project/settings.py` |
| Marking rules (what is a full / half mistake, spelling strictness, accepted variants, 5% / 10% limits) | top of `core/checker.py` |
| Colours, dark mode (pure black), fonts, steno pad | `static/css/style.css` (section 1 = colours) |
| Listening page, timers, draft saving, paste blocking | `static/js/assignment.js` (switches at the top) |
| Page text and layout | `templates/` (every file has comments) |
| Categories (Progressive, Kailashchandra, ...) | `core/models.py` -> `Assignment.CATEGORY_CHOICES` |

After editing `models.py`, run `python manage.py makemigrations` then `python manage.py migrate`.

## Marking rules (core/checker.py)

* Full mistake: word left out, word added or repeated, wrong word, incomplete word, whole word in capitals.
* Half mistake: spelling error, singular/plural slip, missing capital (sentence start / proper noun), missing or misplaced full stop.
* Not counted: commas, semicolons, quotes and other punctuation; 10 vs ten; accepted variants such as Honourable / Hon'ble.
* Mistake % = mistakes / words in the original x 100. Accuracy = 100 - that.

## Passwords the admin can see

The admin "Students" page shows each student's password so the admin can help when someone forgets it.
This is done by storing a readable copy in `UserProfile.plain_password` next to Django's normal hashed password.
The register page tells students about this. To switch it off later, stop writing `plain_password` in
`core/accounts.py` (`create_account`, `set_password`).

## Audio

Use MP3 (works in every browser, including iPhones). Enter the speed the recording was made at when you
upload; the slider changes playback speed relative to it (100 WPM on an 80 WPM recording = 1.25x).

## Tests

```bash
python manage.py test core
```

## Before putting it online

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` and `DJANGO_ALLOWED_HOSTS` as environment variables, serve `/static/`
(`python manage.py collectstatic`) and use HTTPS. Never commit `db.sqlite3` or `media/`.

## Putting it online (Render)

1. Push the project to a GitHub repository (db.sqlite3 and media/ are in .gitignore - keep it that way).
2. render.com -> New -> Web Service -> pick the repository.
3. Settings: Build Command `./build.sh`, Start Command `gunicorn steno_project.wsgi`.
4. Environment variables: `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY=<long random text>`, `PYTHON_VERSION=3.13.5`,
   `OWNER_NAME`, `OWNER_USERNAME`, `OWNER_PHONE`, `OWNER_PASSWORD` (creates the admin on deploy).
5. Free plan warning: the disk is wiped on every deploy/restart, so students, submissions and uploaded
   audio disappear. Fine for a demo; for real use add a paid persistent disk (mounted at the project's
   media folder and db location) or move to PostgreSQL.
