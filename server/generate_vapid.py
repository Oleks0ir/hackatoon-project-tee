import os
import sys

try:
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    from py_vapid.utils import b64urlencode
except ImportError:
    print("Error: py_vapid or cryptography is not installed.")
    print("Please install dependencies first: pip install -r requirements.txt")
    sys.exit(1)

print("Generating VAPID keys...")
vapid = Vapid()
vapid.generate_keys()

# Use a specific name for the VAPID private key to ensure it NEVER overwrites your SSH keys!
private_key_filename = "vapid_private.pem"
private_key_path = os.path.join(os.path.dirname(__file__), private_key_filename)

vapid.save_key(private_key_path)
print(f"1. Saved VAPID private key to: {private_key_path}")

# Get public key base64url representation
raw_pub = vapid.public_key.public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint
)
public_key_base64 = b64urlencode(raw_pub)
if isinstance(public_key_base64, bytes):
    public_key_base64 = public_key_base64.decode('utf-8')


print("\n2. Configuration Output:")
print("----------------------------------------------------------------------")
print("You can add these lines to a file named '.env' inside the server/ directory:")
print("----------------------------------------------------------------------")
print(f'VAPID_PRIVATE_KEY="{private_key_path}"')
print(f'VAPID_PUBLIC_KEY="{public_key_base64}"')
print('VAPID_CLAIM_EMAIL="mailto:your-email@yourdomain.com"')
print("----------------------------------------------------------------------")
print("\nOr, if you prefer to export them directly in your shell session:")
print(f'export VAPID_PRIVATE_KEY="{private_key_path}"')
print(f'export VAPID_PUBLIC_KEY="{public_key_base64}"')
print('export VAPID_CLAIM_EMAIL="mailto:your-email@yourdomain.com"')
print("----------------------------------------------------------------------")
