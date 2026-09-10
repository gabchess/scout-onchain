# Holdout source clarification

This note was written after seeing HLD-01's answer. The frozen suite, rubric and author report remain unchanged.

The answer says the current permanent delegate can change or disable that role, while holding mint authority alone is insufficient. The [Solana overview](https://solana.com/docs/tokens/extensions/permanent-delegate) uses imprecise mint-authority wording. The [official program source](https://raw.githubusercontent.com/solana-program/token-2022/main/program/src/processor.rs) resolves the distinction: the PermanentDelegate branch reads the delegate from that extension and validates it as authority before replacing the value. If no current delegate is present, the branch returns an unsupported-authority error.

The independent reviewer read that primary program source during grading, without inspecting Scout's code. The candidate's more precise claim receives full credit. The original frozen HLD-01-c4 and reference answer required the relevant mint-level authority, and did not require a distinct minting authority to control this change. No score, rubric, or fixture was changed by this clarification. The program's [extension guide](https://www.solana-program.com/docs/token-2022/extensions) also notes that CLI defaults can initially assign the same key to both roles.

This is a documentation-source clarification, not proof of any live mint configuration. The candidate did not inspect live source during its run and should ideally cite the processor or the precise extension guide for this statement.
