# Reliability checklist

Owned by the code owners. Claude reads it but may not edit it (it is protected).
Each item needs a trigger you can see in a diff, a check, and the incident or PR that taught it.
Claude runs only the items whose trigger matches the diff.

The items below are generic starters. Replace them with lessons from this project, and delete any that never fire.

| ID | Trigger (visible in the diff) | Check | Source |
|---|---|---|---|
| C1 | A stored data shape changes (DB column, saved JSON, cache entry, local storage key) | Does old data that lacks the new field still load? Is there a default or a migration? | starter |
| C2 | A database migration is added | Can it run twice safely? Does it lock a large table? Is there a way back? | starter |
| C3 | A new API route or server action | Does it check who the user is and which account or tenant the data belongs to? Is there an integration test? | starter |
| C4 | Logging, analytics or error reporting changes | Could user data, tokens or secrets end up in the logs? | starter |
| C5 | A public API response or event payload changes | Do existing clients still work with the old shape? | starter |
| C6 | Retries, queues, webhooks or payment calls | Is the action safe to run twice (idempotent)? | starter |
| C7 | An environment variable is added or renamed | Is it set in every environment, and is it kept out of browser code if it is secret? | starter |
