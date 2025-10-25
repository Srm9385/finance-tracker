

## Local LLM Finance Tracker – Requirements (v1)

### Technical Specifications
- **Language & Framework**: Python + Jinja templates  
- **Database**: PostgreSQL  
- **Runtime**: `pyenv` managed environment  

--- 

## 0) Purpose & Outcomes

| Goal | Description |
|------|-------------|
| **Primary** | • Budgeting & expense tracking with minimal manual effort.<br>• Accurate, real‑time balances across all accounts.<br>• Natural‑language insights and trend visualisations. |
| **Secondary** | • 100% local operation (no bank APIs or cloud dependencies).<br>• Weekly backups with restore capability.<br>• Full auditability & undo functionality.<br>• Portable on Linux. |

--- 

## 1) Scope (v1)

- Manual CSV imports only – no external APIs.  
- Support ~3 institutions × 4 accounts each + 3 retirement totals.  
- Add new institutions/accounts via a **CSV Mapping Wizard**.  
- Deduplication with conflict review.  
- Merchant normalisation (approval required).  
- Category suggestions by LLM, approval required.  
- Monthly budgeting with caps, roll‑overs to a General Savings bucket, alerts at 75 %.  
- 3‑month deterministic forecasting + scenario planner.  
- Dashboard prioritised views.  
- Read‑only natural‑language chat for Q&A.  
- Weekly backups, exports, audit logs, undo.  
- Local‑only LLM – no external calls.

**Non‑goals (v1)**: bank connections, open banking, bill pay, credit score integration, mobile app, retirement holdings breakdown, dark mode.  

--- 

## 2) Privacy & Hosting

| Item | Detail |
|------|--------|
| Data & inference | Local‑only; never sent outside the machine. |
| Backend | PostgreSQL database. |
| Authentication | Single local user with username/password. |
| Password reset | Edit `config.yaml` to change the password. |
| Encryption at rest | Not implemented in v1 (see section 13). |

--- 

## 3) Institutions, Accounts & Data Ingestion

### Institution/Account Lifecycle
- Create → edit → rename → deactivate / activate.  
- Renames preserve historical data via stable IDs.  
- Deactivation hides the account but keeps all associated records.

### CSV Mapping Wizard

1. **Upload** a sample CSV file.  
2. **Auto‑detect** fields (date, description, amount, balance, …).  
3. **Manual mapping** to required fields.  
4. Configure **date format**, **amount convention**, and **pending/posted handling**.  
5. Run a **validation test** on the first rows.  
6. Set **deduplication / transfer defaults** (inherits global settings).  
7. **Save** as *Mapper v1*; subsequent edits create new versions (*v2*, *v3*, …).  
8. Optionally run a **sample import** to preview results.

### Import Flow
- User selects **Institution → Account** at import time.  
- If header mismatch occurs, prompt the user to update the mapping.  
- An **import log** records: added, updated, skipped, duplicate, and error entries.

### Post‑Import File Archival (v1 Default)

After a successful import, the original CSV is copied to an archive directory and gzipped:

```
~/AI/finance_tracker/archive/<Institution>/<Account>/<YYYY-MM>/<timestamp>__<original_filename>.csv.gz
```

*Archive metadata* stored in the import log:
- Archived path  
- Original filename  
- File size  
- SHA‑256 checksum of the uncompressed source  
- Timestamp  

Duplicate protection is handled via checksum comparison. Failed imports are **not** archived, and archived files are never auto‑deleted.

--- 

## 4) Deduplication

| Rule | Detail |
|------|--------|
| Primary | Exact match on (date, amount, merchant, account). |
| Secondary | Same amount ± 10 days. |
| Resolution | Newest record wins *after user approval*. |
| Review | User reviews duplicates before committing; all decisions are logged. |

--- 

## 5) Accounts & Balances

- **Supported types**: checking, savings, credit cards, loans, retirement (totals only).  
- **Currency**: USD.  
- **Transfers**: mirrored debits/credits ±2 days – always user‑confirmed.  
- CSV running balances are used for validation; discrepancies trigger manual override.

--- 

## 6) Categories

| Emoji | Category Group | Sub‑categories |
|-------|----------------|---------------|
| 🏠 | Housing & Utilities | Rent/Mortgage, Utilities, Internet/Phone, Home Maintenance |
| 🚗 | Transportation | Fuel, Public Transit/Rideshare, Auto Maintenance/Repairs, Insurance (Auto) |
| 🍔 | Food & Dining | Groceries, Dining Out, Coffee/Snacks |
| 👕 | Personal & Lifestyle | Clothing, Health & Fitness, Subscriptions/Streaming, Entertainment |
| 💳 | Financial & Obligations | Loan Payments, Credit Card Payments, Insurance (Non‑Auto), Bank Fees/Interest |
| 🎁 | Giving & Special | Gifts, Donations |
| 💼 | Work & Education | Professional Expenses, Education |
| 💵 | Income | Salary/Wages, Bonus/Commission, Other Income |
| 📊 | Savings & Investments | Emergency Fund (rollover bucket), Retirement Contributions, Other Savings/Investments |

--- 

## 7) Categorisation Hints

- **Merchant ↔ Category**: e.g., “UBER EATS” → Dining Out; “VANGUARD” → Retirement Contributions; “STARBUCKS” → Coffee/Snacks.  
- Refunds/returns offset the original spend in its category.  
- All LLM suggestions require user approval.

--- 

## 8) Budgeting

- **Method**: Simple monthly caps per category.  
- **Roll‑overs**: Unspent funds flow into a General Savings bucket.  
- **Alerts**: Triggered when spending reaches ≥ 75 % of the cap.

--- 

## 9) Forecasting

| Feature | Detail |
|---------|--------|
| Horizon | 3 months |
| Deterministic model | Current balances + recurring items |
| Scenario planner | Allow user to add bonuses, raises, one‑off events |
| Outputs | Projected balances, net worth timeline, cash flow chart |
| Retirement totals | Import cadence flexible (e.g., monthly) but not enforced |

### 9A – Explainability

Every LLM suggestion (categories, normalisations, duplicates, transfers) includes:

- One‑line reason text.  
- Evidence tokens (e.g., “matched UBER EATS”).  
- Confidence band & score.  
- Top 3 alternatives with reasoning.  

For deduplication: match key + date delta.  
For transfers: paired transactions + date delta.

All explanations are persisted in the audit log and transaction detail. A verbosity toggle lets users choose between brief or detailed views. A banner reminds that **“Suggestions require your approval; no changes are saved until you confirm.”**

--- 

## 10) Dashboard & Chat

### Dashboard Priorities
1. Account list with balances & deltas  
2. Net‑worth timeline (incl. retirement totals)  
3. Cash‑flow calendar (upcoming recurring items)  
4. Spend by category (MTD vs prior months)  
5. Income vs expense trend  

Charts: line, bar, donut.

### Chat
- Read‑only Q&A only; no actions are executed via chat.

### Alerts Center
A dedicated panel for reviewing:
- Budget alerts (≥75%)  
- Import issues (mapping changes, parse errors)  
- Dedup/transfer confirmations pending  
- Anomalies (unusual transactions, new merchants)

Alerts can be filtered by type/date and linked to the source view. Users may mark an alert as reviewed without altering data.

--- 

## 11) Backups & Exports

- **Weekly backups** stored in `~/AI/finance_tracker`.  
- Retain the last four snapshots.  
- Each snapshot is a ZIP containing: DB dump, mapper definitions, normalisation approvals, logs, and exports.  
- Export all tables as CSV or JSON.

--- 

## 12) Audit & Undo

| Auditable Event | Description |
|-----------------|-------------|
| Institution/account lifecycle changes | Create / edit / deactivate / activate |
| Mapper versioning | Every wizard save creates a new version |
| Imports | Records of added/updated/skipped entries |
| Deduplication / transfer decisions | User approvals |
| Normalisation approvals | Merchant mapping changes |
| Category changes | LLM suggestions + approvals |
| Budget edits | Cap adjustments, roll‑over settings |
| Balance overrides | Manual corrections |

**Undo** is a multi‑step history per session; users can revert recent changes.

--- 

## 13) Security

- Single local user with username/password.  
- Password reset via editing `config.yaml`.  
- No encryption at rest in v1 (see section 2).

--- 

## 14) Operations

- Weekly backups scheduled automatically.  
- Optional health/status view showing last backup, last import, DB status.

--- 

## 15) Success Criteria (90 days)

1. Balances reflect real‑time data accurately.  
2. Transactions are categorised with minimal corrections.  
3. Dashboard is consulted regularly for insights.  
4. Import overlaps produce no duplicates.  
5. Backups of the last four weeks are fully restorable.

--- 

## 16) MVP vs Later

| Feature | Included in v1 (MVP) | Planned for v2+ |
|---------|---------------------|-----------------|
| Institutions/accounts + mapping wizard | ✅ | – |
| Manual CSV import with dedup review | ✅ | – |
| Merchant normalisation (approval) | ✅ | – |
| Category suggestions + reasoning | ✅ | – |
| Budgets (caps, roll‑overs, alerts) | ✅ | – |
| 3‑month forecast + scenario planner | ✅ | – |
| Dashboard (5 prioritized views) | ✅ | – |
| Read‑only chat Q&A | ✅ | – |
| Backups, exports, audit log, undo | ✅ | – |
| Local‑only LLM | ✅ | – |
| Auto‑watch folders | ✖ | ✔ |
| Regex normalisation rules | ✖ | ✔ |
| Dark mode | ✖ | ✔ |
| Retirement holdings/returns | ✖ | ✔ |
| Investment trend analytics | ✖ | ✔ |
| Push alerts | ✖ | ✔ |
| NAS backups | ✖ | ✔ |
| Encryption at rest | ✖ | ✔ |

--- 

## 17) Natural‑Language Query Intents (Top 10)

1. **“How much did I spend on dining out last month?”** → Category spend query.  
2. **“Show me my grocery spending over the last 3 months.”** → Category trend chart.  
3. **“Which categories are close to going over budget this month?”** → Budget status list.  
4. **“How much is left in my entertainment budget this month?”** → Budget detail.  
5. **“What are my current account balances?”** → Balance overview.  
6. **“What’s my current net worth and how has it changed this year?”** → Net‑worth summary.  
7. **“What will my checking balance look like in 3 months if I keep spending at this rate?”** → Forecast baseline.  
8. **“If I get a $3,000 bonus in December, how will that affect my net worth?”** → Scenario forecast.  
9. **“What’s my income vs expenses trend this year?”** → Income/expense comparison chart.  
10. **“Were there any unusual transactions this month?”** → Anomaly detection report.

--- 

## 18) Open Items

- **CSV field details**: Captured during onboarding via the mapping wizard.  
- **Retirement totals cadence**: User‑driven, flexible.  
- **Alert presentation style**: Currently an Alerts Center; final UI will be refined in design phase.

---

*End of Requirements Document.*