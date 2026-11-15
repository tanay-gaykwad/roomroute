# Contributing to RoomRoute

Thanks for helping improve RoomRoute. The project is focused on rental discovery for students and working professionals in Nagpur.

## Before you start

- For a bug, open an issue with steps to reproduce, what you expected, and what happened. Include your operating system and setup where relevant.
- For a feature, describe the renter or owner problem first. For larger changes, discuss the scope in an issue before writing code.
- Keep changes focused. Avoid submitting real addresses, personal data, credentials, or unlicensed images.

## Development setup

Use Python 3.12 or newer. For a full local service stack, install Docker Desktop and follow the Docker Compose instructions in the README. For a lightweight preview, install `requirements.txt` and run `python server.py`.

## Before opening a pull request

Run the checks that apply to your change:

```powershell
python -m unittest discover -v
python -m py_compile server.py test_server.py
node --check app.js
```

Pull requests should explain the user problem, summarize the change, list the checks run, and mention any migration, security, privacy, or deployment impact. Add or update regression tests when behavior changes. Do not claim checks passed if you did not run them.

All contributions are reviewed before they are merged. By submitting a contribution, you agree that your contribution is provided under the repository's MIT License, subject to applicable law.
