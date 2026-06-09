# Runtime Customization

This folder is the intended place for package-specific agent glue that cannot honestly be solved by generic ANIP runtime code.

- Keep shared runtime libraries generic: parsing, validation, token issuance, invocation, and ANIP outcome handling.
- Put business-language interpretation, package-specific normalization, and routing thresholds in `runtime-overrides.json`.
- Treat `../runtime-customization.json` as generated starter behavior. It can be regenerated; this custom folder is the reviewed app-owned layer.
- Prefer small reviewed rules with examples over endless phrase lists.

Supported sections:

- `normalization.deictic_terms`: words such as `one` or `ones` that should not ground a required entity by themselves.
- `normalization.token_variant_rules`: simple suffix rules used to match business adjectives to reviewed enum/reference values.
- `capability_selection.*`: score thresholds used when the runtime chooses a more precise declared capability after the model's first choice.

- `capability_selection.business_language_rules`: reviewed app-owned wording rules exported from Studio app customization review.
- `capability_selection.selection_hints`: compact reviewed routing hints for package-specific capability selection.

If a behavior is specific to this package, keep it here or in reviewed app-profile metadata. Do not hide it in `anip-runtime-utils`.
