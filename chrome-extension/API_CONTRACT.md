# Chrome Extension API Contract

Generated from `app.openapi()`. Do not edit by hand.

Regenerate:

```
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py
```

---

## `GET /api/users/me`

**Summary:** Read Users Me Route

**Description:** Fetch the current logged in user.

**Responses:**

- `200` — Successful Response

```json
{
  "properties": {
    "disabled": {
      "title": "Disabled",
      "type": "boolean"
    },
    "email": {
      "title": "Email",
      "type": "string"
    },
    "email_verified": {
      "title": "Email Verified",
      "type": "boolean"
    },
    "facebook_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Facebook Url"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "image_urls": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Urls"
    },
    "instagram_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Instagram Url"
    },
    "is_admin": {
      "title": "Is Admin",
      "type": "boolean"
    },
    "is_service_account": {
      "default": false,
      "title": "Is Service Account",
      "type": "boolean"
    },
    "is_superuser": {
      "title": "Is Superuser",
      "type": "boolean"
    },
    "oauth_accounts": {
      "default": [],
      "items": {
        "$ref": "#/components/schemas/OAuthAccountRead"
      },
      "title": "Oauth Accounts",
      "type": "array"
    },
    "reddit_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reddit Url"
    },
    "session_expire_minutes": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Session Expire Minutes"
    },
    "subscription_expires_at": {
      "anyOf": [
        {
          "format": "date-time",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Subscription Expires At"
    },
    "subscription_status": {
      "title": "Subscription Status",
      "type": "string"
    },
    "subscription_tier": {
      "title": "Subscription Tier",
      "type": "string"
    },
    "tiktok_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Tiktok Url"
    },
    "totp_enabled": {
      "default": false,
      "title": "Totp Enabled",
      "type": "boolean"
    },
    "username": {
      "title": "Username",
      "type": "string"
    },
    "youtube_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Youtube Url"
    }
  },
  "required": [
    "id",
    "username",
    "email",
    "disabled",
    "email_verified",
    "is_superuser",
    "is_admin",
    "subscription_tier",
    "subscription_status"
  ],
  "title": "UserRead",
  "type": "object"
}
```


---

## `GET /api/categories/`

**Summary:** Get Categories

**Description:** Get all active categories (seeded from backend source code).

**Responses:**

- `200` — Successful Response

```json
{
  "items": {
    "$ref": "#/components/schemas/CategoryResponse"
  },
  "title": "Response Get Categories Api Categories  Get",
  "type": "array"
}
```


---

## `GET /api/retailers/`

**Summary:** Get Retailers

**Description:** Get all retailers (optionally filtered to active only).

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `active_only` | query | no | boolean |

**Responses:**

- `200` — Successful Response

```json
{
  "items": {
    "$ref": "#/components/schemas/RetailerRead"
  },
  "title": "Response Get Retailers Api Retailers  Get",
  "type": "array"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/retailers/get-or-create`

**Summary:** Get Or Create Retailer By Domain

**Description:** Get existing retailer by domain or create one. For use by scrapers when
adding parts from a retailer not yet in the catalog. Any authenticated user.

**Request body (`application/json`):**

```json
{
  "description": "Request body for get-or-create retailer by domain (scraper use).",
  "properties": {
    "base_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Base URL e.g. https://www.a90shop.com",
      "title": "Base Url"
    },
    "domain": {
      "description": "Domain e.g. a90shop.com",
      "title": "Domain",
      "type": "string"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Display name; derived from domain if omitted",
      "title": "Name"
    }
  },
  "required": [
    "domain"
  ],
  "title": "RetailerGetOrCreateRequest",
  "type": "object"
}
```

**Responses:**

- `200` — Successful Response

```json
{
  "properties": {
    "base_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Base URL (e.g., https://www.a90shop.com)",
      "title": "Base Url"
    },
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "domain": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Domain (e.g., a90shop.com)",
      "title": "Domain"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "is_active": {
      "default": true,
      "description": "Whether the retailer is active",
      "title": "Is Active",
      "type": "boolean"
    },
    "name": {
      "description": "Retailer display name (e.g., A90Shop)",
      "title": "Name",
      "type": "string"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    }
  },
  "required": [
    "name",
    "id",
    "created_at",
    "updated_at"
  ],
  "title": "RetailerRead",
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `GET /api/parts/check-url`

**Summary:** Check Product Url Exists

**Description:** Check if a product URL already exists in the parts catalog.

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `product_url` | query | no | $ref |

**Responses:**

- `200` — URL check completed

```json
{
  "additionalProperties": {
    "anyOf": [
      {
        "format": "uuid",
        "type": "string"
      },
      {
        "type": "null"
      }
    ]
  },
  "title": "Response Check Product Url Exists Api Parts Check Url Get",
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `GET /api/parts/{part_id}`

---

## `GET /api/parts/find-by-part-manufacturer-and-part-number`

**Summary:** Find Part By Part Manufacturer And Part Number Endpoint

**Description:** Find an existing part by part manufacturer and part number (normalized). Returns 404 if not found.

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `part_manufacturer_id` | query | yes | string |
| `part_number` | query | yes | string |

**Responses:**

- `200` — Existing part found

```json
{
  "properties": {
    "best_price_cents": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Lowest current price from any retailer listing (computed when available)",
      "title": "Best Price Cents"
    },
    "canonical_part_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "When set, this part is a duplicate. Clients should redirect or resolve to the referenced canonical part for display.",
      "title": "Canonical Part Id"
    },
    "car_ids": {
      "description": "Car IDs this part is associated with",
      "items": {
        "format": "uuid",
        "type": "string"
      },
      "title": "Car Ids",
      "type": "array"
    },
    "category_id": {
      "format": "uuid",
      "title": "Category Id",
      "type": "string"
    },
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "edit_count": {
      "title": "Edit Count",
      "type": "integer"
    },
    "gtin": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "UPC/EAN/GTIN (digits only)",
      "title": "Gtin"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "image_urls": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Urls"
    },
    "is_universal": {
      "default": false,
      "description": "When True, part fits all cars",
      "title": "Is Universal",
      "type": "boolean"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "part_manufacturer_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Manufacturer Id"
    },
    "part_number": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Number"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    },
    "user_id": {
      "format": "uuid",
      "title": "User Id",
      "type": "string"
    }
  },
  "required": [
    "id",
    "name",
    "category_id",
    "user_id",
    "edit_count",
    "created_at",
    "updated_at"
  ],
  "title": "PartRead",
  "type": "object"
}
```

- `404` — Resource not found
- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/parts/{part_id}/append-images`

**Summary:** Append Images To Part

**Description:** Append image file keys to a part's gallery.

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `part_id` | path | yes | string |

**Request body (`application/json`):**

```json
{
  "properties": {
    "file_keys": {
      "description": "Image references to append: file keys (from images/upload) or external URLs (scraped); max 12.",
      "items": {
        "type": "string"
      },
      "maxItems": 12,
      "title": "File Keys",
      "type": "array"
    }
  },
  "required": [
    "file_keys"
  ],
  "title": "PartAppendImages",
  "type": "object"
}
```

**Responses:**

- `200` — Images appended to part

```json
{
  "properties": {
    "best_price_cents": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Lowest current price from any retailer listing (computed when available)",
      "title": "Best Price Cents"
    },
    "canonical_part_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "When set, this part is a duplicate. Clients should redirect or resolve to the referenced canonical part for display.",
      "title": "Canonical Part Id"
    },
    "car_ids": {
      "description": "Car IDs this part is associated with",
      "items": {
        "format": "uuid",
        "type": "string"
      },
      "title": "Car Ids",
      "type": "array"
    },
    "category_id": {
      "format": "uuid",
      "title": "Category Id",
      "type": "string"
    },
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "edit_count": {
      "title": "Edit Count",
      "type": "integer"
    },
    "gtin": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "UPC/EAN/GTIN (digits only)",
      "title": "Gtin"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "image_urls": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Urls"
    },
    "is_universal": {
      "default": false,
      "description": "When True, part fits all cars",
      "title": "Is Universal",
      "type": "boolean"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "part_manufacturer_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Manufacturer Id"
    },
    "part_number": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Number"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    },
    "user_id": {
      "format": "uuid",
      "title": "User Id",
      "type": "string"
    }
  },
  "required": [
    "id",
    "name",
    "category_id",
    "user_id",
    "edit_count",
    "created_at",
    "updated_at"
  ],
  "title": "PartRead",
  "type": "object"
}
```

- `404` — Resource not found
- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/parts/`

**Summary:** Create Part

**Description:** Create a user-contributed part, optionally with a retailer listing and price.

**Request body (`application/json`):**

```json
{
  "properties": {
    "car_ids": {
      "anyOf": [
        {
          "items": {
            "format": "uuid",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Car IDs this part fits. Ignored when is_universal is True.",
      "title": "Car Ids"
    },
    "category_id": {
      "format": "uuid",
      "title": "Category Id",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "gtin": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "UPC/EAN/GTIN barcode for dedup (digits only stored); e.g. 012345678901",
      "title": "Gtin"
    },
    "image_urls": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "maxItems": 12,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Images: file keys (from images/upload) and/or external URLs (scraped); max 12. First entry is the primary/display image.",
      "title": "Image Urls"
    },
    "is_universal": {
      "default": false,
      "description": "When True, part fits all cars; no need to list car_ids.",
      "title": "Is Universal",
      "type": "boolean"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "part_manufacturer_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Manufacturer/brand for this part. Optional: scraped pages where the brand cannot be confidently determined leave this NULL rather than minting a sentinel 'Unknown' brand row. The DB column is also nullable.",
      "title": "Part Manufacturer Id"
    },
    "part_number": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Number"
    },
    "price_cents": {
      "anyOf": [
        {
          "maximum": 2147483647.0,
          "minimum": 0.0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Price in cents for this retailer (creates/updates listing)",
      "title": "Price Cents"
    },
    "product_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Product URL at retailer (used only with retailer_id for listing)",
      "title": "Product Url"
    },
    "retailer_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Retailer ID when product_url is from a known retailer",
      "title": "Retailer Id"
    }
  },
  "required": [
    "name",
    "category_id"
  ],
  "title": "PartCreate",
  "type": "object"
}
```

**Responses:**

- `200` — Successful Response

```json
{
  "properties": {
    "best_price_cents": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Lowest current price from any retailer listing (computed when available)",
      "title": "Best Price Cents"
    },
    "canonical_part_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "When set, this part is a duplicate. Clients should redirect or resolve to the referenced canonical part for display.",
      "title": "Canonical Part Id"
    },
    "car_ids": {
      "description": "Car IDs this part is associated with",
      "items": {
        "format": "uuid",
        "type": "string"
      },
      "title": "Car Ids",
      "type": "array"
    },
    "category_id": {
      "format": "uuid",
      "title": "Category Id",
      "type": "string"
    },
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "edit_count": {
      "title": "Edit Count",
      "type": "integer"
    },
    "gtin": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "UPC/EAN/GTIN (digits only)",
      "title": "Gtin"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "image_urls": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Urls"
    },
    "is_universal": {
      "default": false,
      "description": "When True, part fits all cars",
      "title": "Is Universal",
      "type": "boolean"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "part_manufacturer_id": {
      "anyOf": [
        {
          "format": "uuid",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Manufacturer Id"
    },
    "part_number": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Number"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    },
    "user_id": {
      "format": "uuid",
      "title": "User Id",
      "type": "string"
    }
  },
  "required": [
    "id",
    "name",
    "category_id",
    "user_id",
    "edit_count",
    "created_at",
    "updated_at"
  ],
  "title": "PartRead",
  "type": "object"
}
```

- `400` — Bad request
- `403` — Not authorized
- `409` — Part already exists
- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/parts/{part_id}/listings`

**Summary:** Create Or Update Part Listing

**Description:** Create or update a retailer listing for a part (and optionally add a price).

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `part_id` | path | yes | string |

**Request body (`application/json`):**

```json
{
  "properties": {
    "part_id": {
      "description": "Part ID",
      "format": "uuid",
      "title": "Part Id",
      "type": "string"
    },
    "price_cents": {
      "anyOf": [
        {
          "minimum": 0.0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Initial price in cents (creates first price history)",
      "title": "Price Cents"
    },
    "product_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Product page URL at this retailer",
      "title": "Product Url"
    },
    "retailer_id": {
      "description": "Retailer ID",
      "format": "uuid",
      "title": "Retailer Id",
      "type": "string"
    }
  },
  "required": [
    "part_id",
    "retailer_id"
  ],
  "title": "PartListingCreate",
  "type": "object"
}
```

**Responses:**

- `200` — Part listing created or updated

```json
{
  "properties": {
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "last_known_price_cents": {
      "anyOf": [
        {
          "minimum": 0.0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "description": "Last known price in cents",
      "title": "Last Known Price Cents"
    },
    "last_price_updated_at": {
      "anyOf": [
        {
          "format": "date-time",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "When last price was observed",
      "title": "Last Price Updated At"
    },
    "part_id": {
      "description": "Part ID",
      "format": "uuid",
      "title": "Part Id",
      "type": "string"
    },
    "product_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Product page URL at this retailer",
      "title": "Product Url"
    },
    "retailer": {
      "properties": {
        "base_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "Base URL (e.g., https://www.a90shop.com)",
          "title": "Base Url"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "domain": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "Domain (e.g., a90shop.com)",
          "title": "Domain"
        },
        "id": {
          "format": "uuid",
          "title": "Id",
          "type": "string"
        },
        "is_active": {
          "default": true,
          "description": "Whether the retailer is active",
          "title": "Is Active",
          "type": "boolean"
        },
        "name": {
          "description": "Retailer display name (e.g., A90Shop)",
          "title": "Name",
          "type": "string"
        },
        "updated_at": {
          "format": "date-time",
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "name",
        "id",
        "created_at",
        "updated_at"
      ],
      "title": "RetailerRead",
      "type": "object"
    },
    "retailer_id": {
      "description": "Retailer ID",
      "format": "uuid",
      "title": "Retailer Id",
      "type": "string"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    }
  },
  "required": [
    "part_id",
    "retailer_id",
    "id",
    "created_at",
    "updated_at",
    "retailer"
  ],
  "title": "PartListingReadWithRetailer",
  "type": "object"
}
```

- `404` — Resource not found
- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `GET /api/part-manufacturers/`

**Summary:** Get Part Manufacturers

**Description:** List part manufacturers.

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `active_only` | query | no | boolean |

**Responses:**

- `200` — Successful Response

```json
{
  "items": {
    "$ref": "#/components/schemas/PartManufacturerResponse"
  },
  "title": "Response Get Part Manufacturers Api Part Manufacturers  Get",
  "type": "array"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/part-manufacturers/`

**Summary:** Create Part Manufacturer

**Description:** Create a manufacturer.

Dedupes by case-insensitive name (and canonical key) so the same brand
isn't minted twice — an existing match is returned instead.

**Request body (`application/json`):**

```json
{
  "description": "User-supplied create payload.",
  "properties": {
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Part manufacturer description",
      "title": "Description"
    },
    "is_active": {
      "default": true,
      "description": "Whether the part manufacturer is active",
      "title": "Is Active",
      "type": "boolean"
    },
    "name": {
      "description": "Part manufacturer name",
      "title": "Name",
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "title": "PartManufacturerCreate",
  "type": "object"
}
```

**Responses:**

- `200` — Successful Response

```json
{
  "properties": {
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "Part manufacturer description",
      "title": "Description"
    },
    "id": {
      "format": "uuid",
      "title": "Id",
      "type": "string"
    },
    "is_active": {
      "default": true,
      "description": "Whether the part manufacturer is active",
      "title": "Is Active",
      "type": "boolean"
    },
    "name": {
      "description": "Part manufacturer name",
      "title": "Name",
      "type": "string"
    },
    "updated_at": {
      "format": "date-time",
      "title": "Updated At",
      "type": "string"
    }
  },
  "required": [
    "name",
    "id",
    "created_at",
    "updated_at"
  ],
  "title": "PartManufacturerResponse",
  "type": "object"
}
```

- `201` — Part Manufacturer created successfully
- `400` — Invalid part manufacturer data
- `403` — Not authorized to create part manufacturer
- `422` — Validation error

---

## `GET /api/car-generations/`

**Summary:** List Entities

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `limit` | query | no | integer |
| `cursor` | query | no | $ref |

**Responses:**

- `200` — Car_Generation page retrieved successfully

```json
{
  "properties": {
    "has_next": {
      "default": false,
      "title": "Has Next",
      "type": "boolean"
    },
    "items": {
      "items": {
        "$ref": "#/components/schemas/CarGenerationRead"
      },
      "title": "Items",
      "type": "array"
    },
    "next_cursor": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Next Cursor"
    }
  },
  "required": [
    "items"
  ],
  "title": "CursorPage[CarGenerationRead]",
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `GET /api/images/by-source-url`

**Summary:** Get Image By Source Url

**Description:** Check if we've already stored an image from this source URL (deduplication).
Returns the existing file_key if found, so clients can skip re-uploading.

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `source_url` | query | yes | string |

**Responses:**

- `200` — Successful Response

```json
{
  "additionalProperties": {
    "type": "string"
  },
  "title": "Response Get Image By Source Url Api Images By Source Url Get",
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/images/upload`

**Summary:** Upload Image

**Description:** Upload an image file to S3 bucket.

The file is validated for security (type, size, content) and stored
in S3 bucket. Returns the file key which should be stored
in your database. Use the /presigned-url endpoint to get a URL for displaying.

Args:
    entity_type: Type of entity (e.g., 'build_list', 'part', 'user', 'car')
    entity_id: Optional ID of the entity (for updates)
    file: Image file to upload
    current_user: Authenticated user (from JWT token)

Returns:
    dict: Contains 'file_key' (store this in your database) and 'presigned_url' (for immediate use)

Raises:
    HTTPException: If upload fails, validation fails, or user is not authenticated

**Parameters:**

| Name | In | Required | Schema |
|------|----|----------|--------|
| `entity_type` | query | yes | string |
| `entity_id` | query | no | $ref |

**Request body (`application/json`):**

```json
{}
```

**Responses:**

- `200` — Successful Response

```json
{
  "additionalProperties": {
    "type": "string"
  },
  "title": "Response Upload Image Api Images Upload Post",
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---

## `POST /api/crawled-pages/scrape`

**Summary:** Scrape Page From Extension

**Request body (`application/json`):**

```json
{
  "properties": {
    "html": {
      "title": "Html",
      "type": "string"
    },
    "url": {
      "title": "Url",
      "type": "string"
    }
  },
  "required": [
    "url",
    "html"
  ],
  "title": "ScrapeRequest",
  "type": "object"
}
```

**Responses:**

- `200` — Successful Response

```json
{
  "properties": {
    "adapter_used": {
      "title": "Adapter Used",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "html_sha256": {
      "default": "",
      "title": "Html Sha256",
      "type": "string"
    },
    "html_size_bytes": {
      "default": 0,
      "title": "Html Size Bytes",
      "type": "integer"
    },
    "image_urls": {
      "default": [],
      "items": {
        "type": "string"
      },
      "title": "Image Urls",
      "type": "array"
    },
    "inferred_category": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Inferred Category"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Name"
    },
    "part_manufacturer": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Manufacturer"
    },
    "part_number": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Part Number"
    },
    "price": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Price"
    },
    "product_url": {
      "title": "Product Url",
      "type": "string"
    }
  },
  "required": [
    "product_url",
    "adapter_used"
  ],
  "title": "ScrapeResponse",
  "type": "object"
}
```

- `413` — HTML payload exceeds the configured maximum UTF-8 byte size.

```json
{
  "properties": {
    "detail": {
      "type": "string"
    }
  },
  "type": "object"
}
```

- `422` — Validation Error

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "title": "Detail",
      "type": "array"
    }
  },
  "title": "HTTPValidationError",
  "type": "object"
}
```


---
