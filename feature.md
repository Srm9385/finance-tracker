# Feature: Transaction Comments

## Overview
Add the ability to attach text comments/notes to individual transactions. This allows users to add context that automated categorization or rules cannot capture (e.g., "Birthday gift for Mom" vs just "Amazon").

## Scope
- **Database**: Add a `comment` field to the `Transaction` model.
- **UI**: Enable inline editing of comments directly within the Transaction List table (Tabulator).
- **Export**: Include comments in CSV exports.
- **Manual Entry**: Allow adding comments when manually creating transactions.
- **Exclusions**: 
  - No CSV import mapping for comments (future enhancement).
  - No AI-generated comments.

## Implementation Plan

### 1. Database Schema
- **File**: `app/models.py`
- **Change**: Add `comment = db.Column(db.Text, nullable=True)` to the `Transaction` model.
- **Migration**:
  1. Run `flask db migrate -m "Add comment field to Transaction"` to generate the migration.
  2. Run `flask db upgrade` to apply it.
  - **Important**: Complete this step and deploy the schema change *before* deploying any backend code that references `Transaction.comment`. Deploying code before the migration runs will cause runtime errors.

### 2. Backend Updates
- **File**: `app/forms.py`
  - Add `comment = TextAreaField("Comment", validators=[Optional(), Length(max=500)])` to `ManualTransactionForm`.
- **File**: `app/blueprints/transactions.py`
  - **Manual Entry**: Update `add_manual` route to save `form.comment.data`.
  - **Inline Edit Endpoint**: Create a new route `PATCH /transaction/<id>` (preferred over a dedicated `/update_comment` route — more extensible if other fields become inline-editable later) to handle AJAX requests for inline edits.
    - Decorate with `@login_required`.
    - Validate the CSRF token. Use `validate_csrf()` or accept a `CSRFOnlyForm` in the request. Do not skip this — the endpoint mutates data.
    - Enforce the 500-character max on `comment` server-side, independent of the form validator.
    - Return a JSON response (e.g., `{"ok": true}` or `{"error": "..."}`) so the frontend can react appropriately.
  - **Export**: Update the CSV export logic to include the `comment` column.
    - Add `"comment"` to the `writer.writerow` header list.
    - Add `txn.comment or ""` to each row's `writer.writerow` call.

### 3. Frontend Updates
- **File**: `app/templates/transactions/list.html`
  - Add a "Comment" column to the Tabulator table configuration.
  - Enable inline editing for the Comment column (using Tabulator's `editable` feature).
  - Implement JavaScript to handle the `cellEdited` event, sending an AJAX request to the inline edit endpoint.
    - Include the CSRF token in the request header (e.g., `X-CSRFToken`).
    - On non-200 response or network error, revert the cell to its previous value using `cell.restoreOldValue()` and show a user-facing error message.
- **File**: `app/templates/transactions/add_manual.html`
  - Add a textarea input for "Comment/Notes" (max 500 characters, `optional`).

## User Flow
1. **View**: User sees a "Comment" column in the transaction list. Empty cells show as blank or "Add note...".
2. **Edit**: User clicks on an empty cell or an existing comment. The cell becomes an input field.
3. **Save**: User types a comment and presses Enter or clicks away. The comment is saved via AJAX without reloading the page. If the save fails, the cell reverts to its previous value.
4. **Export**: When exporting to CSV, the comment is included in the corresponding row.

## Future Considerations
- CSV Import Mapping: Allow users to map a CSV column to the `comment` field during import.
- AI Suggestions: Use AI to suggest comments based on transaction descriptions.
- Search/Filter: Allow filtering transactions by comment text.
