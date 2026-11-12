import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateHeureFr } from '../achats/types'
import { type EtatStock, type LigneStock, type Magasin, type Mouvement, nombre } from './types'

type Article = { id: number; code: string; designation: string }
type Action =
  | { genre: 'inventaire'; ligne: LigneStock }
  | { genre: 'transfert'; ligne: LigneStock }
  | { genre: 'reglage'; ligne: LigneStock }
  | { genre: 'entree' }

/** État du stock par article et par magasin, avec l'historique et, pour le responsable, les corrections. */
export default function Stock() {
  const [etat, setEtat] = useState<EtatStock | null>(null)
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [filtre, setFiltre] = useState({ magasin: '', search: '', alerte: '' })
  const [action, setAction] = useState<Action | null>(null)
  const [saisie, setSaisie] = useState({ quantite: '', motif: '', destination: '', seuil: '', casier: '', article: '', magasin: '', recherche: '' })
  const [articles, setArticles] = useState<Article[]>([])
  const [historique, setHistorique] = useState<{ ligne: LigneStock; mouvements: Mouvement[] } | null>(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    const q = new URLSearchParams(Object.entries(filtre).filter(([, v]) => v))
    api<EtatStock>(`/stock/etat/?${q}`).then(setEtat).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (action?.genre !== 'entree' || saisie.recherche.length < 2) return
    const t = setTimeout(() => {
      api<Page<Article>>(`/articles/?gere_en_stock=true&actif=true&search=${encodeURIComponent(saisie.recherche)}`)
        .then((p) => setArticles(p.results)).catch(() => undefined)
    }, 250)
    return () => clearTimeout(t)
  }, [action, saisie.recherche])

  function ouvrir(a: Action) {
    setErreur('')
    setHistorique(null)
    const l = 'ligne' in a ? a.ligne : null
    setSaisie({ quantite: '', motif: '', destination: '', seuil: l ? String(Number(l.seuil_mini)) : '', casier: l?.casier ?? '', article: '', magasin: filtre.magasin, recherche: '' })
    setArticles([])
    setAction(a)
  }

  async function voirHistorique(ligne: LigneStock) {
    setAction(null)
    const p = await api<Page<Mouvement>>(`/stock/mouvements/?article=${ligne.article}&magasin=${ligne.magasin}`)
    setHistorique({ ligne, mouvements: p.results })
  }

  async function valider(e: FormEvent) {
    e.preventDefault()
    if (!action) return
    setErreur('')
    const poster = (chemin: string, corps: object, method = 'POST') => api(chemin, { method, body: JSON.stringify(corps) })
    try {
      if (action.genre === 'entree') {
        await poster('/stock/mouvements/ajuster/', { article: saisie.article, magasin: saisie.magasin, quantite: saisie.quantite, motif: saisie.motif })
      } else if (action.genre === 'inventaire') {
        await poster('/stock/mouvements/ajuster/', { article: action.ligne.article, magasin: action.ligne.magasin, quantite: saisie.quantite, motif: saisie.motif })
      } else if (action.genre === 'transfert') {
        await poster('/stock/mouvements/transferer/', { article: action.ligne.article, origine: action.ligne.magasin, destination: saisie.destination, quantite: saisie.quantite, motif: saisie.motif })
      } else {
        const corps = { article: action.ligne.article, magasin: action.ligne.magasin, seuil_mini: saisie.seuil || '0', casier: saisie.casier }
        if (action.ligne.reglage) await poster(`/stock/reglages/${action.ligne.reglage}/`, corps, 'PUT')
        else await poster('/stock/reglages/', corps)
      }
      setAction(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  const champ = (k: keyof typeof saisie, v: string) => setSaisie((s) => ({ ...s, [k]: v }))

  if (action) {
    const l = 'ligne' in action ? action.ligne : null
    const titres = { inventaire: 'Inventaire', transfert: 'Transfert vers un autre magasin', reglage: "Seuil d'alerte et rangement", entree: 'Mettre un article en stock' }
    return (
      <form className="fiche" onSubmit={valider}>
        <h2>{titres[action.genre]}</h2>
        {l && <p className="statut">{l.code} · {l.designation} · {l.magasin_nom} · en stock : {nombre(l.quantite)} {l.unite}</p>}
        <fieldset>
          <div className="grille">
            {action.genre === 'entree' && (
              <>
                <label>Chercher l'article (code ou désignation)
                  <input value={saisie.recherche} onChange={(e) => champ('recherche', e.target.value)} />
                </label>
                <label>Article
                  <select required value={saisie.article} onChange={(e) => champ('article', e.target.value)}>
                    <option value="">{articles.length ? 'Choisir…' : 'Tapez au moins 2 lettres'}</option>
                    {articles.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.designation}</option>)}
                  </select>
                </label>
                <label>Magasin
                  <select required value={saisie.magasin} onChange={(e) => champ('magasin', e.target.value)}>
                    <option value="">Choisir…</option>
                    {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
                  </select>
                </label>
              </>
            )}
            {action.genre === 'transfert' && (
              <label>Vers le magasin
                <select required value={saisie.destination} onChange={(e) => champ('destination', e.target.value)}>
                  <option value="">Choisir…</option>
                  {magasins.filter((m) => m.id !== l?.magasin).map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
                </select>
              </label>
            )}
            {action.genre !== 'reglage' && (
              <>
                <label>{action.genre === 'transfert' ? 'Quantité à transférer' : 'Quantité comptée dans le magasin'}
                  <input type="number" required min="0" step="0.01" value={saisie.quantite} onChange={(e) => champ('quantite', e.target.value)} />
                </label>
                <label>Motif{action.genre === 'transfert' ? ' (facultatif)' : ''}
                  <input required={action.genre !== 'transfert'} value={saisie.motif} placeholder={action.genre === 'entree' ? 'Stock de départ' : action.genre === 'inventaire' ? 'Inventaire, casse, erreur…' : ''} onChange={(e) => champ('motif', e.target.value)} />
                </label>
              </>
            )}
            {action.genre === 'reglage' && (
              <>
                <label>Seuil d'alerte (0 : pas d'alerte)
                  <input type="number" min="0" step="0.01" value={saisie.seuil} onChange={(e) => champ('seuil', e.target.value)} />
                </label>
                <label>Rangement (allée, casier)
                  <input value={saisie.casier} maxLength={40} onChange={(e) => champ('casier', e.target.value)} />
                </label>
              </>
            )}
          </div>
          {action.genre === 'inventaire' && <p className="aide">Le stock sera mis à la quantité comptée. L'écart est enregistré dans l'historique.</p>}
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button>Enregistrer</button>
          <button type="button" className="secondaire" onClick={() => { setAction(null); setErreur('') }}>Annuler</button>
        </div>
      </form>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Stock</h2>
        <div className="actions">
          <a className="bouton secondaire" href="#/stock/sorties">Bons de sortie</a>
          {etat?.peut_sortir && <a className="bouton" href="#/stock/sorties/nouvelle">Sortir des pièces</a>}
          {etat?.peut_ajuster && <button className="secondaire" onClick={() => ouvrir({ genre: 'entree' })}>Mettre un article en stock</button>}
        </div>
      </div>
      <div className="grille filtres large">
        <label>Recherche
          <input value={filtre.search} placeholder="Code ou désignation" onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} />
        </label>
        <label>Magasin
          <select value={filtre.magasin} onChange={(e) => setFiltre({ ...filtre, magasin: e.target.value })}>
            <option value="">Tous</option>
            {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
          </select>
        </label>
        <label>Afficher
          <select value={filtre.alerte} onChange={(e) => setFiltre({ ...filtre, alerte: e.target.value })}>
            <option value="">Tout le stock</option>
            <option value="1">Au seuil d'alerte ou en dessous</option>
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!etat && !erreur && <p>Chargement…</p>}
      {etat?.results.length === 0 && <p>{filtre.alerte ? 'Aucun article sous son seuil.' : 'Aucun article en stock.'}</p>}
      {etat && etat.results.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Article</th><th>Magasin</th><th className="nombre">En stock</th><th className="nombre">Seuil</th><th></th></tr></thead>
            <tbody>
              {etat.results.map((l) => (
                <tr key={`${l.article}-${l.magasin}`}>
                  <td>{l.designation}<br /><span className="aide">{l.code}{l.casier && ` · rangement ${l.casier}`}</span></td>
                  <td>{l.magasin_nom}</td>
                  <td className="nombre"><strong>{nombre(l.quantite)}</strong> {l.unite}{l.alerte && <><br /><span className="pastille u1">À réapprovisionner</span></>}</td>
                  <td className="nombre">{Number(l.seuil_mini) > 0 ? nombre(l.seuil_mini) : ''}</td>
                  <td>
                    <div className="actions">
                      <button className="secondaire" onClick={() => voirHistorique(l).catch((e: Error) => setErreur(e.message))}>Historique</button>
                      {etat.peut_ajuster && (
                        <>
                          <button className="secondaire" onClick={() => ouvrir({ genre: 'inventaire', ligne: l })}>Inventaire</button>
                          <button className="secondaire" onClick={() => ouvrir({ genre: 'transfert', ligne: l })}>Transférer</button>
                          <button className="secondaire" onClick={() => ouvrir({ genre: 'reglage', ligne: l })}>Seuil</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {etat && etat.count > etat.results.length && <p className="aide">Seules les {etat.results.length} premières lignes sont affichées : précisez la recherche.</p>}
      {historique && (
        <>
          <h3>Historique : {historique.ligne.designation} · {historique.ligne.magasin_nom}</h3>
          <div className="defilant">
            <table>
              <thead><tr><th>Date</th><th>Mouvement</th><th className="nombre">Quantité</th><th>Détail</th><th>Par</th></tr></thead>
              <tbody>
                {historique.mouvements.map((m) => (
                  <tr key={m.id}>
                    <td>{dateHeureFr(m.date)}</td>
                    <td>{m.type_libelle}</td>
                    <td className="nombre">{Number(m.quantite) > 0 ? '+' : ''}{nombre(m.quantite)}</td>
                    <td>{m.motif}</td>
                    <td>{m.auteur_nom}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
