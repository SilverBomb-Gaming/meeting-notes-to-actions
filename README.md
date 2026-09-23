# meeting-actions by Alfredo Cardona (SilverBomb-Gaming)

A local-first CLI that reads meeting notes (`.txt` or `.md`) and writes action items, decisions, and open questions.

The default model path is [Ollama](https://ollama.com) on your machine (`llama3.2`). No cloud API key is required. The notes stay on localhost unless you opt into an OpenAI-compatible endpoint.

The installable project name is `meeting-notes-to-actions`. The command is `meeting-actions`.

Built by Alfredo Cardona ([SilverBomb-Gaming](https://github.com/SilverBomb-Gaming)).

## In the owner's words

<!-- Replace this paragraph after merge. It is the one spot left for a human voice. -->

I wanted a checklist I could check against the notes without sending them to a hosted model. `--no-llm` only catches lines that are already marked as work, so a messy page of prose stays thin until the Ollama pass, and that pass still has to quote the notes or the program drops the line. That limitation is the one I would explain first.

## What it is / isn't

**It is** a portfolio CLI for one job: turn a notes file into a checklist with a task, an owner when the notes name one, a due date when the notes state one, plus decisions and open questions when the notes actually contain them. Missing owners stay **unassigned**. Missing dates stay **no due date**. JSON uses `null` for both.

**It isn't** a hosted meeting product, a transcription service, or a writer that may invent attendees, owners, deadlines, or decisions. If a quote is not in the file, that item is dropped. If a name or date is not in the quote, that field is cleared. The program does not guess a person or turn "Friday" into a calendar date.

## Demo

For a proper demo, You will need Python 3.11+. Ollama is only required for the last command.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

meeting-actions extract --notes samples/sprint-planning.md --dry-run
```

`--dry-run` prints the notes after newline cleanup and stops. It does not extract and it does not call a model. You should see the heading `# Normalized notes: sprint-planning.md` and the original sentences, including `Alex Rivera will ship the staging deploy by 2026-03-14.`

Write a checklist from explicit lines only (still no model):

```bash
meeting-actions extract --notes samples/sprint-planning.md --no-llm
```

```markdown
# Actions from sprint-planning.md

## Action items

- [ ] Ship the staging deploy — Alex Rivera — due 2026-03-14
- [ ] Write the rollback note — Sam Okonkwo — due Friday
- [ ] Update the on-call roster — Priya Shah — due 2026-03-18

## Decisions

- Keep the staging cluster on the current image until the rollback note is written

## Open questions

- Who covers the pager if Sam is out next Monday?
```

The same extractor on a messier page does not invent an owner or a deadline. `Jordan` is mentioned and is not assigned anything. `someone should clean up the labels` is prose, so it is not promoted to a task. `not decided` does not become a decision.

```bash
meeting-actions extract --notes samples/messy-retro.txt --no-llm --format json
```

`--format` is `markdown` (default) or `json`. `--out actions.md` also writes the stdout text to that file. Stdout is still the document.

```bash
meeting-actions extract --notes samples/sprint-planning.md --no-llm --out actions.md
```

With Ollama, the same file is sent to the model. Hashes are not involved. The check is a verbatim quote:

```bash
ollama pull llama3.2
meeting-actions extract --notes samples/sprint-planning.md --out actions.md
```

`--dry-run` and `--no-llm` together are an error. Both skip the model, and they do different jobs.

## How an extraction is built

```text
.txt / .md  ──►  normalize  ──►  optional model  ──►  grounding check  ──►  markdown or JSON
                 (this program)    (Ollama by default)   (this program)         (this program)
```

1. **Read.** UTF-8 `.txt` or `.md` only. A leading BOM and CRLF are normalized. The words are not rewritten.
2. **Extract, when you ask.** The model receives the notes and must return JSON. The system prompt forbids fabricating attendees, owners, deadlines, or decisions that are not grounded in the notes text. Those sentences are pinned by `tests/test_prompts.py`.
3. **Check in code.** Every kept item needs an evidence quote that appears in the notes. The task, decision, or question has to be supported by that quote. An owner is kept only when that name is in the quote. A due value is kept only when that exact text is in the quote. `someone`, `we`, and `the team` are not owners. A quote that says it was not decided is not a decision.
4. **Fall back.** Unusable model JSON, a model object with no items, or output that the check empties is replaced by the heuristic when the heuristic found something. A warning goes to stderr. If Ollama is down, the command exits with an error instead of pretending the heuristic ran. Use `--no-llm` for that path on purpose.

`--dry-run` stops after step 1. `--no-llm` skips the model and runs the heuristic, then the same grounding check and renderer.

## Heuristic rules

Used by `--no-llm`, and as the fallback. A line becomes an action only when one of these is true:

| Line | What happens |
| --- | --- |
| Markdown checkbox (`- [ ]`, `- [x]`) | Action. The box state is not a status field |
| `TODO:`, `Action:`, `Action item:` | Action |
| `Name will / should / must / needs to / to …` | Action. `Name` is one to three capitalized words and is not `We`, `Someone`, or `The` |
| Bullet `Name: task` | Action, when `Name` passes the same check |
| Next line is only `Owner: Name` | Fills the previous action when that owner is still empty and `Name` is a person |
| Next line is only `Due:` or `Deadline:` | Fills the previous action when the due date is still empty |
| `Decision:` or `We decided` / `We agreed` | Decision. `not decided` is skipped |
| `Question:`, `Open question:`, `Q:`, or a line that ends with `?` | Open question |

Anything else stays in the notes. The heuristic does not promote "someone should …" prose, and it does not read a date out of a heading.

Due text is copied, not calculated:

| In the notes | Due field |
| --- | --- |
| `2026-03-14` | `2026-03-14` |
| `by Friday` | `Friday` |
| `by next week` | `next week` |
| no date on the action | `null` (markdown: `no due date`) |

`Friday` is not turned into an ISO date. An ISO date the model invents is cleared when that date is not in the quote.

## Output

Stdout is this run's text: normalized notes for `--dry-run`, otherwise the checklist or the JSON document.

Markdown sections are always **Action items**, **Decisions**, and **Open questions**. An empty section says so. An action line looks like:

```text
- [ ] Ship the staging deploy — Alex Rivera — due 2026-03-14
- [ ] Capture the incident timeline from the slack thread — unassigned — no due date
```

JSON uses `owner` and `due` as strings or `null`, and includes `evidence` (the quote). Markdown leaves the quote out so the checklist stays pasteable. There is no attendees field.

`--out PATH` replaces that file with the same text. The parent directory must already exist. `--format json` is ignored on `--dry-run`, with a warning on stderr.

## Configuration

Copy `.env.example` to `.env` in the working directory (the directory you run the command from), or export the variables yourself. Existing environment variables win over `.env`.

| Variable | Default | Role |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3.2` | Chat model |
| `OLLAMA_NUM_CTX` | `8192` | Context window sent to Ollama |
| `MEETING_ACTIONS_PROVIDER` | `ollama` | `ollama` or `openai` |
| `MEETING_ACTIONS_TIMEOUT` | `120` | Seconds for the model call |
| `OPENAI_API_KEY` | empty | Only for the OpenAI-compatible path |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Compatible base URL, usually ending in `/v1` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name for that path |

```bash
# Remote or local OpenAI-compatible server (LM Studio, a proxy, api.openai.com, …)
export MEETING_ACTIONS_PROVIDER=openai
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
meeting-actions extract --notes samples/sprint-planning.md
```

`api.openai.com` refuses to run without `OPENAI_API_KEY`. A local compatible server may omit the key. `--provider` and `--model` override the environment for one command.

Notes longer than 100,000 characters are rejected. Split the file. The samples fit easily inside `OLLAMA_NUM_CTX`.

## Scope / out of scope

**In scope**

- One `.txt` or `.md` file per command
- Ollama by default, OpenAI-compatible chat as an option
- A dry run (normalized notes) and a no-model heuristic so you can see a checklist before any model runs
- Action items, decisions, and open questions grounded in quotes from the file

**Out of scope**

- PDF, DOCX, and audio transcription. Those inputs are rejected
- Creating tickets in Jira, Linear, GitHub, or a calendar
- Inventing attendees, owners, deadlines, or decisions that are not in the notes
- Resolving "Friday" or "next week" to a calendar date
- A guarantee that two models will phrase the same task the same way. The quote is the check

## Samples

| File | What it is for |
| --- | --- |
| `samples/sprint-planning.md` | A planning note with named owners, ISO dates, a weekday deadline, one decision, and one open question |
| `samples/messy-retro.txt` | Whiteboard prose. Two explicitly marked tasks with no owner and no date, one real decision, one real question, and several lines that should stay out of the checklist |

## Layout

```text
src/meeting_actions/
  cli.py         # meeting-actions extract …
  notes.py       # .txt / .md loading and normalization
  heuristic.py   # line rules used by --no-llm and as fallback
  prompts.py     # system prompt and the extraction task prompt
  guard.py       # drop quotes, owners, and dates the notes do not support
  extract.py     # model call, fallback, grounding
  render.py      # markdown checklist, JSON, and the dry-run listing
  llm.py         # Ollama and OpenAI-compatible clients
  dotenv.py      # optional .env loader
samples/
tests/           # pytest, no live model
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

`pytest` mocks the model client. It does not start Ollama and does not call the network. Parsing, the schema, the no-fabrication prompt, the heuristic, the grounding check, and the CLI are covered from the samples and from in-memory notes.

Exit codes: `0` success (including a checklist with nothing in it), `1` bad input (missing file, empty file, not `.txt` or `.md`, bad `--format`, `--dry-run` with `--no-llm`), `2` the model provider failed or rejected the configuration.

## License

MIT © 2026 Alfredo Cardona
