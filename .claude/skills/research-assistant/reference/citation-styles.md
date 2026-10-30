# Citation styles

Always follow the target journal's author guidelines first. Most HEC Islamic-studies journals use
**Chicago Manual of Style (notes-bibliography) / Turabian** footnotes; social-science and many
international journals use **APA 7**; some use their own house style (copy a recent published paper of
that journal as the model).

## Chicago notes-bibliography (17th ed.)

| Type | First note | Short note | Bibliography |
|---|---|---|---|
| Book | 1. Wael B. Hallaq, *Sharīʿa: Theory, Practice, Transformations* (Cambridge: Cambridge University Press, 2009), 45. | Hallaq, *Sharīʿa*, 50. | Hallaq, Wael B. *Sharīʿa: Theory, Practice, Transformations*. Cambridge: Cambridge University Press, 2009. |
| Journal article | 2. First Last, "Title," *Journal* 12, no. 3 (2020): 45–67, https://doi.org/... | Last, "Short Title," 50. | Last, First. "Title." *Journal* 12, no. 3 (2020): 45–67. https://doi.org/... |
| Edited classical text | see `islamic-sources.md` | | |
| Thesis | 3. Name, "Title" (M.Phil thesis, University, 2024), 12. | | |
| Website | 4. Author, "Title," Site, date, URL. | | |

"Ibid." is discouraged in Chicago 17 (use short notes) but many Pakistani journals still use it — follow
the journal.

## APA 7

In-text: (Hallaq, 2009, p. 45). Reference list: Hallaq, W. B. (2009). *Sharīʿa: Theory, practice,
transformations*. Cambridge University Press. Classical works: (Ibn Kathīr, 1999/c. 1370) with both dates.

## Urdu and Arabic sources in an English paper

Transliterate the title, optionally add an English translation in square brackets. In an Urdu paper,
Urdu/Arabic references are given in Urdu script; many HEC journals now require **romanised references**
as well (a transliterated bibliography) so that indexing databases can read them — check the guidelines.

## Tooling

- Keep references in `refs.bib` (BibTeX) per article, or `refs.md` if footnotes are hand-written.
- Zotero is the recommended manager for the user (free; Word plugin; exports BibTeX; Chicago & APA styles).
- `rtools.py export draft.md --bib refs.bib --csl <style>.csl` uses pandoc citeproc; CSL files from
  https://github.com/citation-style-language/styles (e.g. `chicago-fullnote-bibliography.csl`, `apa.csl`).
- Pandoc citation syntax in the draft: `[@hallaq2009, 45]`.
