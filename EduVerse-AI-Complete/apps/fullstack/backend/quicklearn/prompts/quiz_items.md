{#
  Quiz item generation (PRD §7.4).

  The distractor instruction is the important part. Random distractors make MCQs trivially
  guessable by elimination and teach nothing; distractors drawn from *adjacent* concepts test
  whether the student can actually tell two neighbouring ideas apart, which is where real
  understanding lives.
#}
Write quiz items testing the concepts below, drawn from {{ title or "this material" }}.

{% if requested_types is defined and requested_types %}
Item types to produce: {{ requested_types | join(", ") }}.
{% endif %}

- `mcq` — exactly {{ mcq_options }} options. `answer` must be the full text of the correct
  option, matching one entry in `options` character for character.
- `cloze` — a sentence with the tested term removed; `answer` is the removed text alone.
- `short` — answerable in a sentence or a formula. `answer` is a reference answer, graded
  leniently on phrasing.
- `free` — requires explanation or derivation. `answer` is a model answer describing what a
  full response must contain.

Rules:

- Produce {{ count }} item(s), spread across the concepts rather than clustered on one.
- Anchor each item to the concept it actually tests (`concept_id`).
- For `mcq`, draw the distractors from `neighbours` or the other concepts in this prompt,
  so the options represent real, related ideas rather than nonsense words.
- `explanation` must cite *why* the right answer is right and why the adjacent distractors
  are wrong, in two sentences or fewer.

Concepts to test:
{% for concept in concepts %}
- Concept {{ concept.id }}: {{ concept.name }} — {{ concept.definition }}
{% endfor %}

Neighbouring concepts (use these for distractors):
{% for neighbour in neighbours %}
- {{ neighbour.name }}: {{ neighbour.definition }}
{% endfor %}
