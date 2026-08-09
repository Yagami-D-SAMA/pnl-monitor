---
name: trade-booking
description: Safely update portfolio trade or dividend history files. Use for every task that books, appends, imports, corrects, or removes transactions in TradeHistory, DvdHistory, or similar investment ledger CSV/XLSX files.
---

# Trade Booking Safety

Follow this workflow before changing any investment transaction ledger.

## Mandatory workflow

1. Read the target file and confirm its schema, encoding, ordering, naming conventions, and sign conventions.
2. Check whether the proposed transaction is already present. Never book a duplicate.
3. Before any write, create a timestamped backup beside the target file.
4. Confirm the backup exists, is readable, and matches the original file size or contents.
5. Make the smallest possible change to the working file.
6. Re-read the updated file and verify:
   - column count and header order are unchanged,
   - the new transaction appears exactly once,
   - quantity, price, fees, currency, consideration, and cost/proceeds signs follow existing conventions,
   - existing rows are unchanged.
7. Report both the updated file and backup path.

## Backup retention rule

Back up the original file before every booking operation. Do not delete the
backup until the user has reviewed the updated file and explicitly approved
deletion.

Never delete, overwrite, rename away, or replace the backup during the booking task. Delete it only after the user explicitly confirms that the updated file has been reviewed and authorizes deletion.

## Missing information

Do not invent identifiers, settlement dates, currency conversions, classifications, or other unavailable transaction fields. Reuse reliable project mappings or matching historical transactions where possible. If a required field cannot be established safely, stop and ask the user.
