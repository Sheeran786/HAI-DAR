# HAI-DAR API Reference (Current Source)

All endpoints are under `/api`. JSON is used for bodies/responses. Auth uses `Authorization: Bearer <JWT>`.

## Public endpoints
| Method | Path | Auth | Request | Response / behavior |
|---|---|---|---|---|
| GET | `/api/` | None | — | Health message |
| GET | `/api/settings` | None | — | Business settings document |
| GET | `/api/products` | None | Query: `search`, `category`, `sort`, `page`, `limit` | `{items,categories,page,has_more}` |
| GET | `/api/products/{product_id}` | None | Path id | Product or 404 |
| POST | `/api/auth/request-otp` | None | Query `mobile` | Dev message + `dev_code=1234`; invalid short mobile → 400 |
| POST | `/api/auth/verify-otp` | None | Query `mobile`, `code` | Customer JWT + user; invalid mobile → 400; non-4-digit code → 401 |
| POST | `/api/auth/admin-login` | None | Query `email`, `password` | Admin JWT + role; bad credentials → 401 |
| POST | `/api/enquiries` | Customer JWT in current implementation | JSON `customer_name,business_name,mobile,whatsapp,city,state,product,required_quantity,message,items[]` | Created enquiry; auth missing → 401 |

## Customer endpoints
| Method | Path | Auth | Request | Response / behavior |
|---|---|---|---|---|
| GET | `/api/orders` | Customer/admin JWT accepted by identity dependency | — | Caller-scoped order list |
| POST | `/api/orders` | Customer/admin JWT accepted by identity dependency | JSON `items,customer_name,business_name,mobile,total` | Created order |
| GET | `/api/orders/{order_id}` | JWT | Path id | Caller-owned order detail; otherwise 404 |
| GET | `/api/enquiries` | JWT | — | Caller-scoped enquiry list |
| GET | `/api/enquiries/{enquiry_id}` | JWT | Path id | Caller-owned enquiry detail; otherwise 404 |

## Admin endpoints
| Method | Path | Auth | Request | Response / behavior |
|---|---|---|---|---|
| GET | `/api/admin/products` | Admin | — | All products |
| POST | `/api/admin/products` | Admin | Product JSON | Creates product |
| PATCH | `/api/admin/products/{product_id}` | Admin | Partial product JSON | Updates product |
| DELETE | `/api/admin/products/{product_id}` | Admin | — | Deletes product |
| GET | `/api/admin/orders` | Admin | — | All orders, newest first |
| PATCH | `/api/admin/orders/{order_id}` | Admin | Query `status`, `tracking` | Updates order status/tracking |
| GET | `/api/admin/enquiries` | Admin | — | All enquiries, newest first |
| PATCH | `/api/admin/enquiries/{enquiry_id}` | Admin | Query `status`, optional `sales_notes` | Updates status/notes |
| GET | `/api/admin/settings` | Admin | — | Settings document |
| PATCH | `/api/admin/settings` | Admin | JSON partial settings | Updates settings |

## Error convention
FastAPI errors return JSON with a `detail` field. Typical codes: 400 for validation, 401 for missing/invalid authentication, 403 for wrong role, 404 for missing resource. Frontend `src/haidar-api.ts` throws `Error(body.detail || "Request failed")` on non-2xx responses.
