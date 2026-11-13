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

async function appeler(chemin: string, options: RequestInit = {}): Promise<Response> {
  const appel = () =>
    fetch(`/api${chemin}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
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
  if (r.status === 403) throw new ErreurApi(403, "Vous n'avez pas le droit d'effectuer cette action.")
  if (!r.ok) {
    // L'API renvoie soit {detail: ...}, soit une erreur par champ.
    const corps = await r.json().catch(() => null)
    const messages = corps ? Object.values(corps).flat().map((m) => (typeof m === 'string' ? m : JSON.stringify(m))) : []
    throw new ErreurApi(r.status, messages.join(' ') || 'Une erreur est survenue.')
  }
  return r
}

export async function api<T>(chemin: string, options: RequestInit = {}): Promise<T> {
  const r = await appeler(chemin, options)
  return r.status === 204 ? (undefined as T) : r.json()
}

/** Ouvre dans un nouvel onglet un fichier protégé par la connexion (un PDF par exemple). */
export async function ouvrirFichier(chemin: string) {
  const onglet = window.open('', '_blank')
  try {
    const url = URL.createObjectURL(await (await appeler(chemin)).blob())
    if (onglet) onglet.location.href = url
    else location.href = url
  } catch (e) {
    onglet?.close()
    throw e
  }
}

/** Enregistre un fichier produit par l'API (Excel) sous le nom donné. */
export async function telechargerFichier(chemin: string, nom: string) {
  const url = URL.createObjectURL(await (await appeler(chemin)).blob())
  const lien = Object.assign(document.createElement('a'), { href: url, download: nom })
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
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
  site: number | null
  service: number | null
  telephone: string
}
export type Service = { id: number; code: string; nom: string }
export type Unite = { id: number; code: string; nom: string }
export type Site = { id: number; code: string; nom: string; ville: string; est_siege: boolean; actif: boolean }
export type Tiers = { id: number; code: string; raison_sociale: string }
