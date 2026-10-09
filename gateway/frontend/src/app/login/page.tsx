'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { apiClient } from '@/lib/client';
import { messageOf } from '@/hooks/useLiveState';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiClient().login(username, password);
      router.replace('/');
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6">
      <h1 className="mb-1 text-2xl font-bold">🌿 GrowHub</h1>
      <p className="mb-8 text-sm text-slate-400">Connexion à votre serre</p>

      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm text-slate-300">
          Nom d’utilisateur
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
          />
        </label>

        <label className="block text-sm text-slate-300">
          Mot de passe
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-rose-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-emerald-600 py-2 font-medium text-white disabled:opacity-50"
        >
          {busy ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-slate-500">
        Pas encore de compte ? Créez-le depuis l’administration Django.
      </p>
    </main>
  );
}
