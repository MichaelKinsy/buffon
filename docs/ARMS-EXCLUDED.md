# Projects not measured

`arms/excluded.toml` lists projects that resemble Pi implementations and are deliberately not arms, each with its reason; the report prints the list in its "Not measured" section. An arm needs a runnable coding agent with a command line Buffon can start against the mock endpoint. A library, an SDK or a model layer has none.

To add a project to Buffon, give it a directory under `arms/` with an `arm.toml` (see CONTRIBUTING.md). To drop one, add it to `excluded.toml` with the reason.
