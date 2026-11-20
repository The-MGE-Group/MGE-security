# Feature map

The verify skill uses this as its guide and its grading sheet. Write each feature from the user's point of view.
Add a row whenever a feature ships. Claude may update this file.

| Feature | Path or entry point | Steps (keys, selectors, requests) | Expected result |
|---|---|---|---|
| Example: sign in | `/login` | fill `#email`, fill `#password`, click `button[type=submit]` | lands on `/dashboard`, shows the user's name |
| Example: create item | `POST /api/items` with `{ "name": "x" }` | as a signed-in user | `201`, item appears in `GET /api/items` |
