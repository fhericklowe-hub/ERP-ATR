import { type FormEvent, useEffect, useState } from 'react'
import { api, connecter, deconnecter, estConnecte, type Page, type Site, type Utilisateur } from './api'

function Connexion({ onConnecte }: { onConnecte: () => void }) {
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function envoyer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setEnCours(true)
    setErreur('')
    try {
      await connecter(String(f.get('username')), String(f.get('password')))
      onConnecte()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <main className="connexion">
      <form onSubmit={envoyer}>
        <h1>ERP</h1>
        <label>
          Identifiant
          <input name="username" autoComplete="username" required autoFocus />
        </label>
        <label>
          Mot de passe
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button disabled={enCours}>{enCours ? 'Connexion…' : 'Se connecter'}</button>
      </form>
    </main>
  )
}

function Sites() {
  const [sites, setSites] = useState<Site[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api<Page<Site>>('/sites/')
      .then((p) => setSites(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [])

  if (erreur) return <p className="erreur">{erreur}</p>
  if (!sites) return <p>Chargement…</p>
  return (
    <table>
      <thead>
        <tr>
          <th>Code</th>
          <th>Site</th>
          <th>Ville</th>
        </tr>
      </thead>
      <tbody>
        {sites.map((s) => (
          <tr key={s.id}>
            <td>{s.code}</td>
            <td>{s.nom}{s.est_siege && ' (siège)'}</td>
            <td>{s.ville}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function App() {
  const [connecte, setConnecte] = useState(estConnecte())
  const [moi, setMoi] = useState<Utilisateur | null>(null)

  useEffect(() => {
    if (!connecte) return
    api<Utilisateur>('/moi/')
      .then(setMoi)
      .catch(() => setConnecte(false))
  }, [connecte])

  if (!connecte) return <Connexion onConnecte={() => setConnecte(true)} />

  function quitter() {
    deconnecter()
    setMoi(null)
    setConnecte(false)
  }

  return (
    <>
      <header>
        <strong>ERP</strong>
        <span>{moi ? `${moi.first_name} ${moi.last_name}`.trim() || moi.username : ''}</span>
        <button onClick={quitter}>Se déconnecter</button>
      </header>
      <main>
        <h2>Sites de l'entreprise</h2>
        <Sites />
      </main>
    </>
  )
}
