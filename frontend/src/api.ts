// Client de l'API : gère les jetons de connexion et leur renouvellement.
const CLE = 'erp.jetons'

type Jetons = { access: string; refresh: string }

function lire(): Jetons | null {
  try {
    return JSON.parse(localStorage.getItem(CLE) ?? 'null')
  } catch {
    return null
  }
}

function ecrire(j: Jetons | null) {
  if (j) localStorage.setItem(CLE, JSON.stringify(j))
  else localStorage.removeItem(CLE)
}

export const estConnecte = () => lire() !== null
export const deconnecter = () => ecrire(null)

export async function connecter(username: string, password: string) {
  const r = await fetch('/api/auth/token/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!r.ok) throw new Error(r.status === 401 ? 'Identifiant ou mot de passe incorrect.' : 'Connexion impossible.')
  ecrire(await r.json())
}

async function renouveler(): Promise<boolean> {
  const j = lire()
  if (!j) return false
  const r = await fetch('/api/auth/token/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: j.refresh }),
  })
  if (!r.ok) return false
  ecrire({ ...j, ...(await r.json()) })
  return true
}

export class ErreurApi extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(chemin: string, options: RequestInit = {}): Promise<T> {
  const appel = () =>
    fetch(`/api${chemin}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${lire()?.access ?? ''}`,
        ...options.headers,
      },
    })
  let r = await appel()
  if (r.status === 401 && (await renouveler())) r = await appel()
  if (r.status === 401) {
    deconnecter()
    throw new ErreurApi(401, 'Session expirée.')
  }
  if (r.status === 403) throw new ErreurApi(403, "Vous n'avez pas le droit d'accéder à ces données.")
  if (!r.ok) throw new ErreurApi(r.status, 'Une erreur est survenue.')
  return r.status === 204 ? (undefined as T) : r.json()
}

export type Page<T> = { count: number; results: T[] }
export type Utilisateur = {
  id: number
  username: string
  first_name: string
  last_name: string
  fonction: string
  roles: string[]
  droits: string[]
}
export type Site = { id: number; code: string; nom: string; ville: string; est_siege: boolean; actif: boolean }
