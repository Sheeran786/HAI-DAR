# HAI-DAR Database Schema (Current Source)

MongoDB is schemaless; there is no migration framework. Startup bootstrap seeds settings/products/admin and creates a unique admin-email index.

## products
- `id` string UUID, public identifier
- `name` string
- `category` string
- `sku` string
- `description` string
- `specifications` string[]
- `packaging` string
- `delivery` string
- `image_data` string[] (currently reserved)
- `variants` array of embedded Variant objects
- `featured` boolean
- `is_new` boolean
- `active` boolean
- `badge` string
- `created_at` ISO UTC string

Variant:
- `id`, `label`, `sku`, `weight`, `moq`, `wholesale_price`, `stock`

## settings
Single document with `id="business"`:
`whatsapp, phone, email, address, delivery_info, announcement`.

## customers
`id, mobile, name, business_name, city, state, created_at`.

## admins
`id, email, password_hash, created_at`.
Unique index on `email`.

## orders
`id` human-readable order id, `customer_id`, `items[]`, `customer_name`, `business_name`, `mobile`, `total`, `status`, `tracking`, `created_at`.

## enquiries
`id`, `customer_id`, `customer_name`, `business_name`, `mobile`, `whatsapp`, `city`, `state`, `product`, `required_quantity`, `message`, `items[]`, `status`, `sales_response`, `sales_notes`, `created_at`.

## otp_codes
Current development OTP request writes `mobile`, `code="dev"`, `created_at`. The verify endpoint does not actually compare this record; any 4-digit numeric code passes.

## Relationships
- `orders.customer_id -> customers.id`
- `enquiries.customer_id -> customers.id`
- `orders.items[].product_id -> products.id`
- `products.variants[]` is embedded; no variants collection
- categories are derived from `products.category`; no categories collection
