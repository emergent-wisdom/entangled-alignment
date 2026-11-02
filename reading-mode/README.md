# The reading mode

An optional add-on for the Meaning Model, for reading a book as a first reader does: read a little, think when a new idea comes up, tend to the model and its graph. It is not part of the Meaning Model. It lives here and is loaded only for a reading.

It does three things a prompt cannot: it holds back the text not yet read, it measures the time used, and it names the perspectives for each stretch of text. How to model stays in the run's prompt and the tool's own guidance.

## Loading it

It needs a Meaning Model that loads add-ons by path. Give the server three settings:

```sh
MEANING_MODEL_ADDONS=storytelling,/absolute/path/to/reading-mode/reading-mode.mjs
READING_MODE_PARAMETERS=/absolute/path/to/parameters.json
LIFE_SIM_STATE_FILE=/absolute/path/to/store/meaning-model.sqlite
```

Then tell the model to get the text with `life_reading_next`. Nothing else gives it the book.

The mode uses nothing from the storytelling add-on. It is loaded beside it because a reading models lives, and those tools and guides come from storytelling and the tool's `source_reconstruction` purpose.

## Tools

- **`life_reading_next`** gives the next whole paragraphs. Ask with `paragraphs`, or with `chars` for the paragraphs that come closest to that many characters; with neither, one paragraph. It returns:
  - the text;
  - the path of a file holding it, which `life_document_import` takes as `sourcePath`;
  - how far the reading has got and the time used against the target;
  - the Workers for this stretch.
  At the end it says the book ends; at `stop_at_chars` it says the reading pauses and the book goes on.
- **`life_reading_status`** gives the same progress and the last text again, so a resumed session can pick up.

## Parameters

| Key | Default | Meaning |
|---|---|---|
| `source` | required | The book as UTF-8 text, paragraphs separated by blank lines. A relative path is read from the parameter file's folder. |
| `perspectives` | none | The Workers to rotate through, in a fixed order that the seed shuffles. |
| `perspectives_per_stretch` | `2` | How many Workers each stretch names. |
| `seed` | `20261009` | Shuffles the Workers as Python's `random.Random(seed).shuffle` does, so the order matches the paper's readings. |
| `stretch_chars` | `4000` | The Workers change every this many characters of text. A read names the Workers of every stretch it covers, so small reads repeat a pair and long reads skip none. |
| `time_limit_hours` | `4` | The time target the progress line reports against. It paces; it does not stop anything. |
| `stop_at_chars` | `0` | For a test: pause at the first paragraph end at or past this many characters. `0` reads to the end. |
| `state_folder` | the store's path plus `.reading` | Where the position, the reads, the time and the text files handed out are kept. |

Time used is the sum of the server's sessions, so time between sessions does not count.

[`metamorphosis.json`](metamorphosis.json) is the parameter set for the Kafka reading.

## What holds and what does not

Only text already handed out leaves the mode. The source's path is named only in the parameter file, and the parameter file only in the server's settings, so the model is never told where the book is.

Two limits stay:
- `life_document_import` reads any absolute path the model names, so the hold rests on the model not knowing the path.
- The model may remember a famous book. Nothing here can separate a forecast from recall.
