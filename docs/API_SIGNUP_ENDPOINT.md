# HealthPrep Signup API Documentation

## Overview
The HealthPrep Signup API allows external websites (such as the marketing website) to integrate with the HealthPrep onboarding system. This API creates new organizations and initiates the Stripe checkout process.

## Endpoint

### POST /api/signup

Creates a new organization and returns a Stripe checkout URL for payment setup.

**URL:** `https://your-healthprep-domain.com/api/signup`

**Method:** `POST`

**Content-Type:** `application/json`

**CORS:** Enabled for all origins (configure specific domains in production)

**CSRF:** Exempt (no CSRF token required)

## Request Body

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `organization_name` | string | Name of the medical organization | "Downtown Medical Center" |
| `admin_email` | string | Email address of the primary admin | "admin@downtown-medical.com" |
| `specialty` | string | Medical specialty or practice type | "Cardiology" |
| `epic_client_id` | string | **REQUIRED** - Epic FHIR client ID | "abc123xyz" |
| `epic_client_secret` | string | **REQUIRED** - Epic FHIR client secret | "secret_key_here" |
| `epic_fhir_url` | string | **REQUIRED** - Epic FHIR base URL | "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/" (sandbox) or custom production URL |
| `epic_environment` | string | Environment type: "sandbox" or "production" | "sandbox" (default) or "production" |
| `terms_agreed` | boolean | Must be `true` - indicates acceptance of terms | true |

### Optional Fields

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `site_location` | string | Physical location or site name | "" | "Downtown Campus" |
| `phone_number` | string | Contact phone number | "" | "555-1234" |
| `address` | string | Physical address | "" | "123 Main St, City, ST 12345" |
| `billing_email` | string | Separate billing email | Uses admin_email | "billing@downtown-medical.com" |

### Epic FHIR Credentials Guidance

**⚠️ REQUIRED FOR ALL SIGNUPS:** 
- Organizations MUST obtain Epic FHIR credentials before signing up
- All three Epic fields (`epic_client_id`, `epic_client_secret`, `epic_fhir_url`) are mandatory
- Signup will fail if any Epic credential is missing

**Environment-Specific URLs:**
- **Sandbox (default):** Use `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/`
- **Production:** Each hospital has a unique Epic FHIR endpoint (e.g., `https://hospital-name.epic.com/FHIR/api/FHIR/R4/`)
- **Production organizations CANNOT use the sandbox URL** - they must provide their organization-specific FHIR endpoint from their Epic representative

## Example Requests

### Example 1: Signup WITH Epic Credentials (Sandbox)

```bash
curl -X POST https://your-healthprep-domain.com/api/signup \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "Downtown Medical Center",
    "admin_email": "admin@downtown-medical.com",
    "specialty": "Cardiology",
    "site_location": "Downtown Campus",
    "phone_number": "555-1234",
    "address": "123 Main St, City, ST 12345",
    "billing_email": "billing@downtown-medical.com",
    "epic_client_id": "abc123xyz",
    "epic_client_secret": "secret_key_here",
    "epic_fhir_url": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/",
    "epic_environment": "sandbox",
    "terms_agreed": true
  }'
```

### Example 2: Production Organization with Custom FHIR URL

```bash
curl -X POST https://your-healthprep-domain.com/api/signup \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "University Hospital System",
    "admin_email": "admin@university-hospital.edu",
    "specialty": "Multi-Specialty",
    "epic_client_id": "prod_client_xyz",
    "epic_client_secret": "prod_secret_here",
    "epic_fhir_url": "https://university-hospital.epic.com/FHIR/api/FHIR/R4/",
    "epic_environment": "production",
    "terms_agreed": true
  }'
```

## Success Response

**Status Code:** `200 OK`

**Response Body:**

```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "organization_id": 123
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` on success |
| `checkout_url` | string | Stripe checkout URL - redirect user here to complete payment |
| `organization_id` | integer | Unique ID of the created organization |

### Next Steps After Success

1. Redirect the user to the `checkout_url` to complete Stripe payment setup
2. After Stripe checkout, HealthPrep sends a welcome email with password setup link
3. User can log in and configure organization while awaiting root admin approval

## Error Responses

### 400 Bad Request - Missing Content-Type

```json
{
  "success": false,
  "error": "Content-Type must be application/json"
}
```

### 400 Bad Request - Missing Required Fields

```json
{
  "success": false,
  "error": "Missing required fields: organization_name, admin_email, specialty"
}
```

### 400 Bad Request - Missing Epic Credentials

```json
{
  "success": false,
  "error": "Epic FHIR credentials are required: epic_client_id, epic_client_secret, and epic_fhir_url must all be provided"
}
```

### 400 Bad Request - Invalid FHIR URL Format

```json
{
  "success": false,
  "error": "Invalid epic_fhir_url format. Must be a valid URL starting with http:// or https://"
}
```

### 400 Bad Request - Production Using Sandbox URL

```json
{
  "success": false,
  "error": "Production organizations cannot use the sandbox FHIR URL. Please provide your organization's unique Epic FHIR endpoint from your Epic representative."
}
```

### 400 Bad Request - Terms Not Agreed

```json
{
  "success": false,
  "error": "You must agree to the terms and conditions"
}
```

### 400 Bad Request - Duplicate Organization Name

```json
{
  "success": false,
  "error": "Organization name already exists"
}
```

### 400 Bad Request - Duplicate Email

```json
{
  "success": false,
  "error": "Email address already registered"
}
```

### 400 Bad Request - Stripe Error

```json
{
  "success": false,
  "error": "Unable to process payment setup. Please try again later."
}
```

### 500 Internal Server Error

```json
{
  "success": false,
  "error": "An unexpected error occurred"
}
```

## Integration Guide

### JavaScript/TypeScript Example

```javascript
async function signupOrganization(formData) {
  try {
    const response = await fetch('https://your-healthprep-domain.com/api/signup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        organization_name: formData.orgName,
        admin_email: formData.email,
        specialty: formData.specialty,
        site_location: formData.siteLocation,
        phone_number: formData.phone,
        epic_client_id: formData.epicClientId,
        epic_client_secret: formData.epicClientSecret,
        epic_fhir_url: formData.epicFhirUrl,  // REQUIRED
        epic_environment: formData.epicEnvironment || 'sandbox',  // sandbox or production
        terms_agreed: formData.termsAccepted
      })
    });

    const data = await response.json();

    if (data.success) {
      // Redirect to Stripe checkout
      window.location.href = data.checkout_url;
    } else {
      // Display error message to user
      alert(data.error);
    }
  } catch (error) {
    alert('Network error. Please try again.');
  }
}
```

### HTML Form Example

```html
<form id="signup-form">
  <input type="text" name="organization_name" required placeholder="Organization Name">
  <input type="email" name="admin_email" required placeholder="Admin Email">
  <input type="text" name="specialty" required placeholder="Specialty">
  
  <!-- Epic FHIR Credentials (REQUIRED) -->
  <select name="epic_environment" required>
    <option value="sandbox" selected>Sandbox (Testing)</option>
    <option value="production">Production (Live)</option>
  </select>
  <input type="url" name="epic_fhir_url" required placeholder="Epic FHIR Base URL" 
         value="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/">
  <input type="text" name="epic_client_id" required placeholder="Epic Client ID">
  <input type="password" name="epic_client_secret" required placeholder="Epic Client Secret">
  
  <input type="checkbox" name="terms_agreed" required> I agree to the terms
  <button type="submit">Sign Up</button>
</form>

<script>
document.getElementById('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  
  const response = await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      organization_name: formData.get('organization_name'),
      admin_email: formData.get('admin_email'),
      specialty: formData.get('specialty'),
      epic_environment: formData.get('epic_environment'),
      epic_fhir_url: formData.get('epic_fhir_url'),
      epic_client_id: formData.get('epic_client_id'),
      epic_client_secret: formData.get('epic_client_secret'),
      terms_agreed: formData.get('terms_agreed') === 'on'
    })
  });
  
  const data = await response.json();
  if (data.success) {
    window.location.href = data.checkout_url;
  } else {
    alert(data.error);
  }
});
</script>
```

## Security Considerations

1. **HTTPS Only:** Always use HTTPS in production to protect sensitive data
2. **Client Secrets:** Epic client secrets are encrypted before storage
3. **CSRF Exempt:** This endpoint is exempt from CSRF protection to allow cross-origin requests
4. **Email Verification:** Welcome emails are sent after successful Stripe checkout
5. **Rate Limiting:** Consider implementing rate limiting on your marketing website

## Workflow Overview

1. **Marketing Website** → POST /api/signup → **HealthPrep API**
2. **HealthPrep API** → Creates organization & admin user → Returns checkout_url
3. **Marketing Website** → Redirects user → **Stripe Checkout**
4. **User** → Completes payment setup → **Stripe**
5. **Stripe** → Webhook → **HealthPrep** → Sends welcome email
6. **Admin User** → Sets password → Logs in → Configures organization
7. **Root Admin** → Reviews setup → Approves organization → Trial starts

## Support

For technical issues or questions about this API, contact HealthPrep support or consult the main documentation.
