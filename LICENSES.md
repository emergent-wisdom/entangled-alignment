# License Map

This repository contains software, operational prompts, publication material,
research artifacts, and third-party source texts. The applicable terms depend
on the path.

## MIT License

The following original software and operational materials are licensed under
the [MIT License](LICENSE):

- root shell scripts, configuration files, package manifests, lock files, and
  dependency specifications
- Python source and supporting analysis code under
  `chronological_metacognition/`, excluding `material/`, `traces/`, and
  generated research artifacts
- the operational prompt suite under `prompts/`
- `paper/emergentwisdom.sty` and `paper/emergentwisdom-longform.sty`

## Creative Commons Attribution 4.0

The following original research and publication material is licensed under
[Creative Commons Attribution 4.0 International](LICENSE-CONTENT), only to the
extent that Henrik Westerberg holds the relevant copyright or database rights:

- `README.md`
- the paper TeX source, bibliography, figures, and PDFs under `paper/`, except
  for the style files listed above
- the duplicate rendered paper under `output/pdf/`
- `chronological_metacognition/figures.tex`
- released traces under `chronological_metacognition/traces/`
- generated Markdown, metadata, databases, and other research artifacts under
  `projects/`

Suggested attribution: Henrik Westerberg, *Entangled Alignment: When Safety Is
the Substrate* (2026), using the DOI of the version consulted.

The CC BY license does not relicense quoted or embedded source passages,
third-party works, model-provider output, software dependencies, or any other
material for which Henrik Westerberg does not hold the relevant rights.

## Excluded and separately licensed material

- `chronological_metacognition/material/metamorphosis.txt` is a Project
  Gutenberg edition and is governed by the terms embedded in that file.
- `chronological_metacognition/material/llada.tex` is third-party paper source
  for *Large Language Diffusion Models*. It is not licensed under either of
  this repository's licenses.
- Generated traces and graph artifacts may reproduce passages from those two
  source works. Rights in those passages remain with their respective rights
  holders.
- `orchestrator/` is a Git submodule governed by its own `LICENSE` file.
- Installed and declared dependencies retain their respective upstream terms.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for source details.
