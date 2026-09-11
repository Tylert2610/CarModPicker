/**
 * The passkeys panel for identity mode: enrol, rename, delete.
 *
 * Modelled on WebbPulse-Portfolio's `components/admin/PasskeysPanel.tsx`, which
 * serves the same three operations against the same package.
 *
 * ## Why this is a separate component from the existing passkeys tab
 *
 * `./PasskeySettings` speaks CarModPicker's own WebAuthn routes through
 * `@simplewebauthn/browser`: it fetches options and a `challenge_token`, runs
 * the ceremony in the page, and posts the credential back with that token. The
 * identity service holds the challenge server side against the session and the
 * package runs both legs inside one call, so there is no token for this
 * component to carry and no second request for it to make.
 *
 * The two also disagree about what a credential is called. The legacy summary
 * carries a `nickname` and an integer id; a package `Passkey` carries a `name`
 * and a base64url `credentialId`, which is what the rename and delete routes
 * take. One component holding both would branch at every field, so there are
 * two and `./SecuritySettingsDialog` picks one. Row 13 deletes the legacy one
 * whole.
 *
 * ## The last credential rule
 *
 * The server refuses to delete the only credential on an account that has no
 * other way in, and its refusal sentence names the next step. This panel shows
 * that sentence rather than a generic failure, which is the whole reason
 * `../../api/identityPasskeys` keeps the server's message.
 */
import { useCallback, useEffect, useState } from 'react';
import { FaKey, FaPencilAlt, FaPlus, FaTrash } from 'react-icons/fa';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';
import {
  deletePasskey,
  enrolPasskey,
  listPasskeys,
  passkeysSupported,
  renamePasskey,
  type Passkey,
} from '../../api/identityPasskeys';

/** A date for display, falling back to the raw value rather than throwing. */
const formatDate = (value: string | undefined): string => {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
};

function IdentityPasskeySettings() {
  const [passkeys, setPasskeys] = useState<Passkey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const supported = passkeysSupported();

  const load = useCallback(async () => {
    const result = await listPasskeys();
    if (result.status === 'ok') {
      setPasskeys(result.value);
    } else if (result.status === 'failed') {
      setError(result.error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAdd = async () => {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const result = await enrolPasskey(newName);
      if (result.status === 'ok') {
        setSuccess(`Passkey "${result.value.name}" added.`);
        setShowAddForm(false);
        setNewName('');
        await load();
      } else if (result.status === 'failed') {
        setError(result.error);
      }
      // A cancellation is silent. The user dismissed the browser's own sheet
      // and already knows what happened; an error banner would only argue.
    } finally {
      setBusy(false);
    }
  };

  const handleRename = async (credentialId: string) => {
    const name = editName.trim();
    if (name === '') {
      setError('Give your passkey a name.');
      return;
    }
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const result = await renamePasskey(credentialId, name);
      if (result.status === 'ok') {
        setSuccess('Passkey renamed.');
        setEditing(null);
        setEditName('');
        await load();
      } else if (result.status === 'failed') {
        setError(result.error);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (passkey: Passkey) => {
    if (
      !window.confirm(
        `Remove "${passkey.name}"? You will not be able to sign in with it again.`
      )
    ) {
      return;
    }
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const result = await deletePasskey(passkey.credentialId);
      if (result.status === 'ok') {
        setSuccess('Passkey removed.');
        await load();
      } else if (result.status === 'failed') {
        // Includes the last-credential refusal, whose sentence names the next
        // step. See the module note.
        setError(result.error);
      }
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Passkeys</h3>
        <p className="text-sm text-muted-foreground">
          Sign in with your fingerprint, face, screen lock or a security key
          instead of a password.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}
      {success && <ConfirmationAlert message={success} />}

      {!supported && (
        <p className="text-sm text-muted-foreground">
          This browser cannot use passkeys. Your existing passkeys are listed
          below and still work in a browser that can.
        </p>
      )}

      {passkeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          You have not added a passkey yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {passkeys.map((passkey) => (
            <li
              key={passkey.credentialId}
              className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
            >
              {editing === passkey.credentialId ? (
                <>
                  <Input
                    aria-label="Passkey name"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    disabled={busy}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => void handleRename(passkey.credentialId)}
                    disabled={busy}
                  >
                    Save
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setEditing(null);
                      setEditName('');
                    }}
                    disabled={busy}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <>
                  <div className="flex min-w-0 items-center gap-3">
                    <FaKey className="shrink-0 text-primary" />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-white">
                        {passkey.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Added {formatDate(passkey.createdAt)}
                        {passkey.lastUsedAt
                          ? ` · Last used ${formatDate(passkey.lastUsedAt)}`
                          : ''}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      aria-label={`Rename ${passkey.name}`}
                      onClick={() => {
                        setEditing(passkey.credentialId);
                        setEditName(passkey.name);
                        setError(null);
                        setSuccess(null);
                      }}
                      disabled={busy}
                    >
                      <FaPencilAlt />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      aria-label={`Remove ${passkey.name}`}
                      onClick={() => void handleDelete(passkey)}
                      disabled={busy}
                    >
                      <FaTrash />
                    </Button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {showAddForm ? (
        <div className="space-y-3 rounded-lg border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="passkey-name"
            className="block text-sm font-medium text-foreground"
          >
            Name this passkey
          </label>
          <Input
            id="passkey-name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Laptop, phone, security key"
            disabled={busy}
          />
          <div className="flex gap-2">
            <Button
              type="button"
              onClick={() => void handleAdd()}
              disabled={busy}
              loading={busy}
            >
              {busy ? 'Waiting for your device…' : 'Add passkey'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowAddForm(false);
                setNewName('');
              }}
              disabled={busy}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        supported && (
          <Button
            type="button"
            onClick={() => {
              setShowAddForm(true);
              setError(null);
              setSuccess(null);
            }}
            disabled={busy}
          >
            <FaPlus />
            <span>Add a passkey</span>
          </Button>
        )
      )}
    </div>
  );
}

export default IdentityPasskeySettings;
