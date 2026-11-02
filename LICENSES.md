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
- the reading mode under `reading-mode/`
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
- original generated readings and evaluation records under `results/`,
  excluding the third-party source texts and software identified below

Original analysis and verification scripts and operational prompt files under
`results/` use the MIT License. Source texts retain the rights notices supplied
with their editions.

Suggested attribution: Henrik Westerberg, *Entangled Alignment: When Safety Is
the Substrate* (2026), using the DOI of the version consulted.

The CC BY license does not relicense quoted or embedded source passages,
third-party works, model-provider output, software dependencies, or any other
material for which Henrik Westerberg does not hold the relevant rights.

## Excluded and separately licensed material

- `chronological_metacognition/material/metamorphosis.txt` is a Project
  Gutenberg edition and is governed by the terms embedded in that file.
- `results/kafka-2026-10/source/metamorphosis-johnston.txt` is extracted from
  the Ian Johnston translation identified in that folder. The exact source
  PDF states that the document is in the public domain; its source and rights
  record are supplied with the text.
- Generated traces and graph artifacts may reproduce passages from their two
  source works: the edition above and *Large Language Diffusion Models*
  (arXiv:2502.09992), whose source is available from arXiv. Rights in those passages remain with their respective rights
  holders.
- `orchestrator/` is a Git submodule governed by its own `LICENSE` file.
- Installed and declared dependencies retain their respective upstream terms.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for source details.
