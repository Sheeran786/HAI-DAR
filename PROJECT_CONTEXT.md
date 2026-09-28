# HAI-DAR Project Context — AI Continuation

## Mission
Continue the existing HAI-DAR B2B wholesale mobile/web application. This is an existing working project. Do NOT rebuild from scratch, redesign the UI, replace the architecture, or invent business data. Make surgical changes only when explicitly requested.

## Current architecture
- Frontend: Expo 57.0.24 + Expo Router 57.0.22 + React Native 0.86.3 + TypeScript.
- Backend: FastAPI 0.110.1 + Uvicorn + Motor 3.3.1.
- Database: MongoDB.
- Auth: HS256 JWT, 14-day expiry; bcrypt/passlib for admin password verification.
- Package manager: Yarn 1.22.22 for frontend.
- Frontend API base: `EXPO_PUBLIC_BACKEND_URL`, then `/api` is appended by `src/haidar-api.ts`.
- App is a single main Expo route: `frontend/app/index.tsx`; most UI/state/business orchestration is in that file.
- Backend is intentionally concentrated in `backend/server.py`.

## Data collections
1. `products`
2. `settings`
3. `customers`
4. `admins`
5. `orders`
6. `enquiries`
7. `otp_codes` (legacy/mock OTP storage)

Products contain embedded `variants[]`; there is no separate variants collection and no categories collection. Categories are derived from active products.

## Authentication
### Customer
- `POST /api/auth/request-otp?mobile=...` returns development OTP metadata.
- `POST /api/auth/verify-otp?mobile=...&code=...` accepts any 4-digit numeric code in the current implementation; it does not compare the submitted code with the stored `otp_codes` document.
- Customer JWT role is `customer`.
- Native token storage uses Expo SecureStore; web secure helpers fall back to AsyncStorage.
- User profile data is stored separately in general storage.

### Admin
- `POST /api/auth/admin-login?email=...&password=...`
- Admins are seeded at startup from environment variables.
- Admin JWT role is `admin`.
- Admin token is stored separately from customer token.
- `/api/admin/*` routes require admin role.

## Customer features currently implemented
- Splash
- Home/catalogue
- Product listing
- Search
- Category filter
- Sorting
- Product detail
- Embedded variants
- Variant MOQ and price display
- Quantity stepper
- Bulk cart
- Order creation
- Customer order list/detail
- Enquiry list/detail
- Bulk enquiry form
- WhatsApp deep link
- Profile/login/logout
- Admin access entry from Profile

## Admin features currently implemented
- Admin login
- Protected control room
- Product list/create/update/delete
- Orders queue
- Enquiries queue
- Settings read/update
- WhatsApp/phone/email/address/delivery/announcement settings
- Product fields include featured/new/active/badge, variants, MOQ, price, stock and image_data.

There is NO dedicated admin customer-management route in the current API.

## Order workflow
`Enquiry Received -> Order Confirmed -> Processing -> Packed -> Dispatched -> Delivered`

Orders are stored in `orders.status`. Admin can update status and tracking with:
`PATCH /api/admin/orders/{order_id}?status=...&tracking=...`

Customer order detail is:
`GET /api/orders/{order_id}`

## Enquiry workflow
Enquiries use the same six status values. Current backend `POST /api/enquiries` requires a valid JWT, despite older handover/PRD wording describing anonymous enquiry as supported. The current frontend also requires customer login before submission.

## Critical verified limitations
1. Admin Orders/Enquiries are list-only in the current UI. Rows are not tappable and there is no admin detail screen.
2. Backend has no `GET /api/admin/orders/{id}` or `GET /api/admin/enquiries/{id}` route.
3. Admin enquiry PATCH currently accepts `status` and `sales_notes`; `sales_response` is not writable by that route.
4. OTP is development-only and accepts any 4-digit numeric code.
5. Cart is React state only; it is not persisted server-side or to storage.
6. Product images are placeholders/text cards; `image_data[]` exists but there is no upload UI.
7. Admin queues are not paginated.
8. MOQ is enforced/displayed in the client flow, but `POST /api/orders` does not enforce MOQ server-side.
9. Stock is display-only; order creation does not reserve/decrement stock.
10. There is no payment, shipping, invoice, push notification, real SMS OTP, or production object-storage integration.

## Verification level
- Static source inspection: performed on the supplied 62-file export.
- Python syntax compilation: `backend/server.py` and both backend test modules compile successfully.
- Full pytest execution was NOT completed in this environment because the runtime reported missing `pytest-xdist`; therefore no claim of live endpoint/test-suite success is made here.
- Frontend TypeScript build was not executed because the supplied export intentionally excludes `node_modules` and Yarn was not available in this inspection runtime.

## Continuation rules
1. Read `HANDOVER.md`, then `backend/server.py`, then `frontend/app/index.tsx`.
2. Preserve current UI and architecture.
3. Do not create a replacement app.
4. Do not change database field names casually.
5. Ask before major architectural changes.
6. Never hard-code secrets.
7. Never invent product, pricing, customer, admin or business data.
8. Prefer surgical bug fixes over refactors.
9. Preserve the separate customer/admin token namespaces.
10. Preserve `/api` routing unless a migration is explicitly requested.
