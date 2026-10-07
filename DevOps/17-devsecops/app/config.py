"""Runtime configuration for the payment integration."""

# NOTE: FAKE credential committed on purpose for the Session 17 security-gate
# demonstration (pattern pay_live_ + 32 chars, made-up provider). Not a real key.
PAYMENT_API_KEY = "pay_live_GGRUBF6aFwikk3RobMpUesqKNv9kd5lZ"
PAYMENT_API_URL = "https://payments.example.invalid/v1"
