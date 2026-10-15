# Constructed examples

These fictional coordination exercises demonstrate software behavior. They are
not experimental protocols or validated handling instructions.

- `mixed-run.json` assigns two different workstreams, two named people, a shared
  device and a fixed external booking. It includes exact and bounded waiting gaps.
- `pinned-run.json` keeps observed starts from the same exercise, moves the planning
  frontier to 650 elapsed seconds, and replans only unfixed tasks.
- `impossible.json` cannot fit two three-minute uses of one exclusive resource
  into a five-minute horizon with the declared fixed start and release.

All three files are also installed in the wheel and available through
`bench-window example --name NAME --out new-file.json`.
