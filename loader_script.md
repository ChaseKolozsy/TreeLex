### Plan for Uploading Hungarian Words and Phrases

1. **Data Preparation:**
   - Collect a list of Hungarian words and the phrases they are found in.
   - Generate up to 10 definitions for each word in Hungarian.

2. **Matching Words with Definitions:**
   - For each word in a phrase, attempt to match it with one of its definitions.
   - If matched, mark it as familiar.
   - If not matched, mark it as unfamiliar.

3. **Handling Short Words:**
   - For words less than 4 letters, check if they are prepositions.
   - If they are prepositions, verify their definitions through additional checks.

4. **Seeding the Database:**
   - For words greater than 3 letters, assume a single definition for initial seeding.
   - Populate the `Phrases` table with phrases and update it with `lemma_references` and correctly enumerated lemmas based on the matched definitions.

5. **Review and Verification:**
   - Review the populated database to ensure accuracy.
   - Make any necessary adjustments or corrections.
