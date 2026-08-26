"""FastAPI tool backend.

Every query endpoint reads through the `rri_readonly` role -- defense in
depth even if application-level validation is bypassed. The design rule
"every metric carries its source" becomes a required `sources` field in
the response envelope; see `api/envelope.py`.
"""
