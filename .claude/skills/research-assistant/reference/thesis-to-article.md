# From M.Phil thesis to journal article

A thesis chapter proves you know the field; an article proves one point. Never submit a chapter as is.

## Steps

1. **Map the thesis** (`research/thesis/map.md`): for each chapter list its claim, sources, pages, and whether
   it is background (rarely publishable) or analysis/findings (publishable).
2. **Pick the strongest unit**: usually the analytical chapter or the findings, not the introduction or
   biography chapters.
3. **Reframe** around a single question. Write the one-sentence contribution.
4. **Update the literature**: add work published after the thesis was written and the international
   (English/Arabic) literature the thesis may have skipped. Reviewers notice old literature reviews.
5. **Cut** background a specialist reader knows. Compress the scholar's biography to a paragraph.
6. **Deepen** the analysis: comparison, critique, application, a table that organises the findings.
7. **Rewrite in fresh prose.** Same research, new text. Never paste paragraphs from the thesis: the thesis
   is very likely in Turnitin's database (HEC repository / university submission), so copied text shows up
   as a high similarity match.
8. **Disclose**: add a note (usually first footnote or acknowledgement): "This article is derived from the
   author's M.Phil thesis, *[title]*, [University], [year], supervised by [name]." Many journals require it;
   it also explains any residual overlap.
9. **Authorship**: in Pakistan, a thesis-based paper commonly lists the supervisor as co-author. Ask the user
   what the university and supervisor expect; decide before submission, not after.
10. Run `rtools.py overlap draft.md thesis.md` and aim for very low n-gram overlap (see `integrity.md`).

## One thesis, several papers

Possible splits (check which fit the actual thesis):
- the analytical core → main article (best journal);
- a methodological / comparative angle → second article;
- a literature review of the field → review article (international journals welcome these);
- an application to a current issue → third article.
Each paper needs its own question and must not duplicate another (no "salami slicing").
