# Marketing Website Integration Update
## Breaking Change: epic_fhir_url Now Required

**Date:** December 2024  
**Priority:** HIGH - Requires immediate update to marketing website signup form

---

## Summary of Changes

The `/api/signup` endpoint now **requires** the `epic_fhir_url` field for all organization signups. This change aligns with Epic's multi-tenancy architecture where each healthcare organization has a unique FHIR base URL.

### What Changed

**Before:**
- `epic_fhir_url` was optional
- System defaulted to sandbox URL if not provided
- No validation on this field

**After:**
- `epic_fhir_url` is **REQUIRED**
- No default fallback - must be explicitly provided
- API returns 400 error if missing

---

## Required Marketing Website Updates

### 1. Update Signup Form Fields

Add the following new field to your signup form:

```html
<!-- Epic Environment Selector -->
<div class="form-group">
  <label for="epic_environment">
    Epic Environment <span class="required">*</span>
  </label>
  <select 
    id="epic_environment" 
    name="epic_environment" 
    class="form-control" 
    onchange="handleEnvironmentChange()" 
    required
  >
    <option value="sandbox" selected>Sandbox (Testing)</option>
    <option value="production">Production (Live Patient Data)</option>
  </select>
  <small class="form-text text-muted">
    Select sandbox for testing or production for live healthcare data
  </small>
</div>

<!-- Epic FHIR Base URL -->
<div class="form-group">
  <label for="epic_fhir_url">
    Epic FHIR Base URL <span class="required">*</span>
  </label>
  <input 
    type="url" 
    id="epic_fhir_url" 
    name="epic_fhir_url" 
    class="form-control" 
    value="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/" 
    required
  />
  <small class="form-text text-muted" id="fhir_url_help">
    Sandbox URL provided. For production, contact your Epic representative for your organization's unique FHIR endpoint.
  </small>
</div>
```

### 2. Add JavaScript Helper Function

```javascript
function handleEnvironmentChange() {
  const environment = document.getElementById('epic_environment').value;
  const urlField = document.getElementById('epic_fhir_url');
  const helpText = document.getElementById('fhir_url_help');
  
  if (environment === 'sandbox') {
    // Auto-fill sandbox URL and lock it
    urlField.value = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/';
    urlField.readOnly = true;
    helpText.textContent = 'Sandbox URL provided for testing environment.';
  } else {
    // Clear field and allow custom input for production
    urlField.value = '';
    urlField.readOnly = false;
    urlField.placeholder = 'https://your-hospital.epic.com/FHIR/api/...';
    helpText.textContent = 'Enter your organization\'s unique Epic FHIR endpoint provided by your Epic representative.';
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', handleEnvironmentChange);
```

### 3. Update API Request Payload

Your API call must now include `epic_fhir_url`:

```javascript
const payload = {
  organization_name: formData.organizationName,
  admin_email: formData.email,
  specialty: formData.specialty,
  site_location: formData.siteLocation || null,
  phone_number: formData.phone || null,
  address: formData.address || null,
  billing_email: formData.billingEmail || null,
  epic_client_id: formData.epicClientId,
  epic_client_secret: formData.epicClientSecret,
  epic_fhir_url: formData.epicFhirUrl,  // ← NOW REQUIRED
  terms_agreed: formData.termsAccepted
};

const response = await fetch('https://health-prep-v-201-mitchfusillo.replit.app/api/signup', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(payload)
});
```

### 4. Handle New Error Response

The API now returns a specific error for missing `epic_fhir_url`:

```javascript
const data = await response.json();

if (!data.success) {
  // Handle specific epic_fhir_url error
  if (data.error.includes('epic_fhir_url')) {
    alert('Please provide your Epic FHIR endpoint URL. Contact your Epic representative if you don\'t have this information.');
  } else {
    alert(data.error);
  }
}
```

---

## Complete Updated Example

### Full HTML Form

```html
<form id="healthprep-signup-form">
  <!-- Organization Details -->
  <input type="text" name="organization_name" required placeholder="Organization Name">
  <input type="text" name="specialty" required placeholder="Specialty">
  
  <!-- Contact Information -->
  <input type="email" name="admin_email" required placeholder="Admin Email">
  
  <!-- Epic FHIR Integration -->
  <h4>Epic FHIR Credentials</h4>
  <p class="help-text">
    Contact your Epic representative to obtain these credentials before signing up.
  </p>
  
  <select id="epic_environment" name="epic_environment" onchange="handleEnvironmentChange()" required>
    <option value="sandbox" selected>Sandbox (Testing)</option>
    <option value="production">Production (Live)</option>
  </select>
  
  <input 
    type="url" 
    id="epic_fhir_url" 
    name="epic_fhir_url" 
    value="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/" 
    required 
  />
  <small id="fhir_url_help">Sandbox URL provided.</small>
  
  <input type="text" name="epic_client_id" required placeholder="Epic Client ID">
  <input type="password" name="epic_client_secret" required placeholder="Epic Client Secret">
  
  <!-- Terms -->
  <label>
    <input type="checkbox" name="terms_agreed" required>
    I agree to the Terms and Conditions
  </label>
  
  <button type="submit">Start Free Trial</button>
</form>

<script>
function handleEnvironmentChange() {
  const environment = document.getElementById('epic_environment').value;
  const urlField = document.getElementById('epic_fhir_url');
  const helpText = document.getElementById('fhir_url_help');
  
  if (environment === 'sandbox') {
    urlField.value = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/';
    urlField.readOnly = true;
    helpText.textContent = 'Sandbox URL provided for testing.';
  } else {
    urlField.value = '';
    urlField.readOnly = false;
    urlField.placeholder = 'https://your-hospital.epic.com/FHIR/api/...';
    helpText.textContent = 'Enter your unique Epic FHIR endpoint from your Epic representative.';
  }
}

document.getElementById('healthprep-signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  
  const payload = {
    organization_name: formData.get('organization_name'),
    admin_email: formData.get('admin_email'),
    specialty: formData.get('specialty'),
    epic_client_id: formData.get('epic_client_id'),
    epic_client_secret: formData.get('epic_client_secret'),
    epic_fhir_url: formData.get('epic_fhir_url'),  // REQUIRED
    terms_agreed: formData.get('terms_agreed') === 'on'
  };
  
  try {
    const response = await fetch('https://health-prep-v-201-mitchfusillo.replit.app/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    
    if (data.success) {
      // Redirect to Stripe checkout
      window.location.href = data.checkout_url;
    } else {
      alert(data.error);
    }
  } catch (error) {
    alert('Network error. Please try again.');
  }
});

// Initialize environment behavior
document.addEventListener('DOMContentLoaded', handleEnvironmentChange);
</script>
```

---

## API Error Responses

### Missing epic_fhir_url

```json
{
  "success": false,
  "error": "epic_fhir_url is required. Please provide your organization's Epic FHIR endpoint URL."
}
```

### Invalid Request (All Required Fields)

```json
{
  "success": false,
  "error": "Missing required fields: organization_name, admin_email, specialty, epic_client_id, epic_client_secret, epic_fhir_url"
}
```

---

## Testing Guidance

### Test Case 1: Sandbox Signup (Recommended for Testing)

```json
{
  "organization_name": "Test Clinic",
  "admin_email": "admin@testclinic.com",
  "specialty": "Family Practice",
  "epic_client_id": "test_client_123",
  "epic_client_secret": "test_secret_456",
  "epic_fhir_url": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/",
  "terms_agreed": true
}
```

### Test Case 2: Production Signup

```json
{
  "organization_name": "Memorial Hospital",
  "admin_email": "admin@memorial.org",
  "specialty": "Cardiology",
  "epic_client_id": "abc-xyz-production",
  "epic_client_secret": "prod_secret_789",
  "epic_fhir_url": "https://memorial-hospital.epic.com/FHIR/api/FHIR/R4/",
  "terms_agreed": true
}
```

---

## Migration Timeline

**Immediate Action Required:**
1. Update marketing website signup form with new fields
2. Test with sandbox environment
3. Deploy to production

**Backward Compatibility:**  
⚠️ **NONE** - The API will reject requests without `epic_fhir_url`

---

## Support & Questions

For technical questions or implementation help:
- Review full API documentation: `docs/API_SIGNUP_ENDPOINT.md`
- Contact HealthPrep development team
- Test using: `https://health-prep-v-201-mitchfusillo.replit.app/api/signup` (development)

---

## Key Takeaways

✅ **DO:**
- Add environment selector (Sandbox/Production)
- Auto-fill sandbox URL and lock field for sandbox environment
- Require manual input for production FHIR URLs
- Validate epic_fhir_url is not empty before submission
- Guide users to contact Epic representative for production URLs

❌ **DON'T:**
- Send null or empty epic_fhir_url
- Assume sandbox URL works for all signups
- Skip validation on the frontend

---

**Questions?** Contact the HealthPrep technical team or review the updated API documentation.
