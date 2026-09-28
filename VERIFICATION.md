# HAI-DAR Handover Verification

## Export
- Source export supplied: `haidar-handover(1).zip`
- Source files: 62
- Original export size: 1,410,928 bytes
- Final sanitized backup removes the hard-coded admin test password from two regression test files.
- No real `.env` files are present in the supplied export.

## Static verification
- backend/server.py: compile FAILED: compile() missing required argument 'filename' (pos 2)
- backend/tests/backend_test.py: compile FAILED: compile() missing required argument 'filename' (pos 2)
- backend/tests/test_admin_auth.py: compile FAILED: compile() missing required argument 'filename' (pos 2)
- Test functions found: 29
- Route decorators found: 22
- Frontend app is concentrated in `frontend/app/index.tsx` (365 lines).
- Backend is concentrated in `backend/server.py` (493 lines).

## Important source-level findings
- Admin Orders GET exists and returns the full queue.
- Admin Order detail GET does NOT exist.
- Admin Order rows in the frontend are rendered as non-clickable summary rows.
- Customer order list and customer order detail routes exist.
- Customer login token is persisted using the storage wrapper.
- Admin token is persisted separately using the storage wrapper.
- Product CRUD writes to the same MongoDB used by public catalogue reads.
- Admin customer-management API is NOT present.
- Current `/api/enquiries` creation requires JWT; anonymous submission is not actually supported by the current backend/frontend.
- Current OTP verification accepts any 4-digit numeric code.
- Current server-side order creation does not enforce MOQ or stock.

## Runtime verification limitations
The complete pytest suite was not run in this environment because the runtime lacked the `pytest-xdist` plugin even though it is listed in `backend/requirements.txt`. Frontend dependency installation/build was not run because the export intentionally excludes `node_modules` and the inspection runtime did not have a usable Yarn executable. Therefore this package distinguishes source-level verification from live-runtime verification.
