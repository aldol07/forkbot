"""Users' own provider keys: load (decrypted) for an account."""
import uuid

from sqlalchemy import select

from ..crypto import decrypt
from ..models import ProviderKey


def load_user_keys(db, owner_id: uuid.UUID) -> dict[str, str]:
    keys = {}
    for row in db.scalars(select(ProviderKey).where(ProviderKey.owner_id == owner_id)):
        plain = decrypt(row.key_encrypted)
        if plain:  # undecryptable (secret rotated) = treated as missing
            keys[row.provider] = plain
    return keys
