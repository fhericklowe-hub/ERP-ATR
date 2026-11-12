import { type FormEvent, useEffect, useState } from 'react'
import Detail from './achats/Detail'
import DetailCommande from './achats/DetailCommande'
import FormulaireCommande from './achats/FormulaireCommande'
import ListeCommandes from './achats/ListeCommandes'
import DetailReception from './achats/DetailReception'
import FormulaireReception from './achats/FormulaireReception'
import ListeReceptions from './achats/ListeReceptions'
import Formulaire from './achats/Formulaire'
import Liste from './achats/Liste'
import { api, connecter, deconnecter, estConnecte, type Utilisateur } from './api'

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
        <img src="/logo.png" alt="ATR" width="180" />
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

function useRoute() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const maj = () => setHash(location.hash)
    addEventListener('hashchange', maj)
    return () => removeEventListener('hashchange', maj)
  }, [])
  return hash.replace(/^#/, '') || '/'
}

function Page({ moi }: { moi: Utilisateur }) {
  const route = useRoute()
  if (route === '/demandes/nouvelle') return <Formulaire moi={moi} />
  const modif = route.match(/^\/demandes\/(\d+)\/modifier$/)
  if (modif) return <Formulaire moi={moi} id={Number(modif[1])} />
  const detail = route.match(/^\/demandes\/(\d+)$/)
  if (detail) return <Detail id={Number(detail[1])} moiId={moi.id} droits={moi.droits} />
  if (route.split('?')[0] === '/commandes') return <ListeCommandes key={route} />
  if (route === '/receptions') return <ListeReceptions />
  const recevoir = route.match(/^\/commandes\/(\d+)\/recevoir$/)
  if (recevoir) return <FormulaireReception commandeId={Number(recevoir[1])} />
  const modifBr = route.match(/^\/receptions\/(\d+)\/modifier$/)
  if (modifBr) return <FormulaireReception id={Number(modifBr[1])} />
  const br = route.match(/^\/receptions\/(\d+)$/)
  if (br) return <DetailReception id={Number(br[1])} />
  const nouveauBon = route.match(/^\/demandes\/(\d+)\/commander$/)
  if (nouveauBon) return <FormulaireCommande demandeId={Number(nouveauBon[1])} />
  const modifBon = route.match(/^\/commandes\/(\d+)\/modifier$/)
  if (modifBon) return <FormulaireCommande id={Number(modifBon[1])} />
  const bon = route.match(/^\/commandes\/(\d+)$/)
  if (bon) return <DetailCommande id={Number(bon[1])} />
  return <Liste />
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
        <a href="#/" className="marque"><img src="/logo.png" alt="ATR" height="36" /><strong>ERP</strong></a>
        <nav>
          <a href="#/">Demandes d'achat</a>
          <a href="#/commandes">Bons de commande</a>
          <a href="#/receptions">Bons de réception</a>
        </nav>
        <span>{moi ? `${moi.first_name} ${moi.last_name}`.trim() || moi.username : ''}</span>
        <button onClick={quitter}>Se déconnecter</button>
      </header>
      <main>
        {moi && <Page moi={moi} />}
      </main>
    </>
  )
}
