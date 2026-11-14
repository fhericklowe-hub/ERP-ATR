import { type FormEvent, useEffect, useRef, useState } from 'react'
import { api, type Page } from '../api'
import type { Magasin } from './types'

type Succursale = { code: string; articles: number; quantite: string; magasin: number | null }
type Bilan = { lues: number; articles_crees: number; stocks_modifies: number; inchanges: number; erreurs: string[]; avertissements: string[]; succursales: Succursale[]; simulation: boolean; ecrit: boolean }

/** Stock de départ ou inventaire complet d'un magasin, depuis un classeur Excel. On contrôle d'abord, on importe ensuite. */
export default function ImportStock() {
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [magasin, setMagasin] = useState('')
  const [bilan, setBilan] = useState<Bilan | null>(null)
  const [assoc, setAssoc] = useState<Record<string, string>>({})
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const fichier = useRef<HTMLInputElement>(null)
  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
  }, [])

  async function envoyer(simuler: boolean, e?: FormEvent) {
    e?.preventDefault()
    const f = fichier.current?.files?.[0]
    if (!f) return setErreur('Choisissez le fichier.')
    const corps = new FormData()
    corps.set('fichier', f)
    if (magasin) corps.set('magasin', magasin)
    corps.set('succursales', JSON.stringify(Object.fromEntries(Object.entries(assoc).filter(([, v]) => v))))
    if (simuler) corps.set('simuler', '1')
    setErreur('')
    setEnCours(true)
    try {
      setBilan(await api<Bilan>('/stock/mouvements/importer/', { method: 'POST', body: corps }))
    } catch (err) {
      setBilan(null)
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pret = bilan?.simulation && bilan.erreurs.length === 0 && bilan.lues > 0
  return (
    <form className="fiche" onSubmit={(e) => envoyer(true, e)}>
      <p><a href="#/stock">← Stock</a></p>
      <h2>Importer un stock depuis Excel</h2>
      <fieldset>
        <p className="aide">
          Première feuille du classeur, titres sur la première ligne utile : <strong>Code (ou Référence), Désignation, Unité, Quantité</strong>, puis au besoin
          Seuil, Rangement, Prix (ou PMP). Les articles inconnus sont créés. Le stock du magasin est mis à la quantité du fichier ;
          les articles absents du fichier ne sont pas touchés. Un export de logiciel de stock avec les colonnes <strong>Succursale</strong> et
          <strong>Constructeur</strong> est reconnu : vous associez chaque succursale à un magasin, les lignes d'un même article sont additionnées
          et le prix est le prix moyen pondéré.
        </p>
        <div className="grille">
          <label>Magasin (si le fichier n'a pas de colonne Succursale)
            <select value={magasin} onChange={(e) => { setMagasin(e.target.value); setBilan(null) }}>
              <option value="">Choisir…</option>
              {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
            </select>
          </label>
          <label>Classeur Excel (.xlsx)
            <input ref={fichier} type="file" accept=".xlsx" required onChange={() => setBilan(null)} />
          </label>
        </div>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {bilan && bilan.succursales.length > 0 && (
        <fieldset>
          <legend>Succursales du fichier</legend>
          <div className="grille">
            {bilan.succursales.map((x) => (
              <label key={x.code}>Succursale {x.code} ({x.articles} article(s), {Number(x.quantite).toLocaleString('fr-FR')} en stock)
                <select value={assoc[x.code] ?? (x.magasin ? String(x.magasin) : '')} onChange={(e) => { setAssoc({ ...assoc, [x.code]: e.target.value }); setBilan({ ...bilan, simulation: false }) }}>
                  <option value="">Choisir le magasin…</option>
                  {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
                </select>
              </label>
            ))}
          </div>
          <p className="aide">Après avoir choisi les magasins, cliquez sur « Contrôler le fichier » de nouveau.</p>
        </fieldset>
      )}
      {bilan && (
        <fieldset>
          <legend>{bilan.ecrit ? 'Import terminé' : bilan.erreurs.length ? 'Fichier à corriger : rien n\'a été importé' : 'Contrôle réussi'}</legend>
          <p role="status">
            {bilan.lues} ligne(s) lue(s) · {bilan.articles_crees} article(s) {bilan.ecrit ? 'créé(s)' : 'à créer'} ·{' '}
            {bilan.stocks_modifies} stock(s) {bilan.ecrit ? 'modifié(s)' : 'à modifier'} · {bilan.inchanges} inchangé(s)
          </p>
          {bilan.avertissements.length > 0 && <ul>{bilan.avertissements.map((x) => <li key={x} className="aide">{x}</li>)}</ul>}
          {bilan.erreurs.length > 0 && <ul>{bilan.erreurs.map((x) => <li key={x} className="erreur">{x}</li>)}</ul>}
        </fieldset>
      )}
      <div className="actions">
        <button className={pret ? 'secondaire' : ''} disabled={enCours}>{enCours ? 'Lecture…' : 'Contrôler le fichier'}</button>
        {pret && <button type="button" disabled={enCours} onClick={() => envoyer(false)}>Importer</button>}
      </div>
    </form>
  )
}
