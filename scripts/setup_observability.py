"""Generate private local development credentials; never prints them."""
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'instance/langfuse.env'
path.parent.mkdir(exist_ok=True)
keys = ('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'CLICKHOUSE_PASSWORD', 'MINIO_PASSWORD',
        'NEXTAUTH_SECRET', 'LANGFUSE_SALT', 'LANGFUSE_ENCRYPTION_KEY', 'LANGFUSE_PUBLIC_KEY',
        'LANGFUSE_SECRET_KEY', 'LANGFUSE_USER_PASSWORD')
if not path.exists():
    path.write_text('\n'.join(f'{key}={secrets.token_hex(32)}' for key in keys) + '\nLANGFUSE_ENABLED=true\nLANGFUSE_BASE_URL=http://127.0.0.1:3000\n')
    path.chmod(0o600)
print('Local credentials stored in ignored instance/langfuse.env (existing file preserved).')
