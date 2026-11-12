import { type FormEvent, useEffect, useRef, useState } from 'react'
import { api, type Page } from '../api'
import type { Magasin } from './types'

type Bilan = { lues: number; articles_crees: number; stocks_modifies: number; inchanges: number; erreurs: string[]; simulation: boolean; ecrit: boolean }

/** Stock de départ ou inventaire complet d'un magasin, depuis un classeur Excel. On contrôle d'abord, on importe ensuite. */
export default function ImportStock() {
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [magasin, setMagasin] = useState('')
  const [bilan, setBilan] = useState<Bilan | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const fichier = useRef<HTMLInputElement>(null)
  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
  }, [])

  async function envoyer(simuler: boolean, e?: FormEvent) {
    e?.preventDefault()
    const f = fichier.current?.files?.[0]
    if (!f || !magasin) return setErreur('Choisissez le magasin et le fichier.')
    const corps = new FormData()
    corps.set('fichier', f)
    corps.set('magasin', magasin)
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
          Première feuille du classeur, titres en première ligne : <strong>Code, Désignation, Unité, Quantité</strong>, puis au besoin
          Seuil, Rangement, Prix. Les articles inconnus sont créés. Le stock du magasin est mis à la quantité du fichier ;
          les articles absents du fichier ne sont pas touchés.
        </p>
        <div className="grille">
          <label>Magasin
            <select required value={magasin} onChange={(e) => { setMagasin(e.target.value); setBilan(null) }}>
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
      {bilan && (
        <fieldset>
          <legend>{bilan.ecrit ? 'Import terminé' : bilan.erreurs.length ? 'Fichier à corriger : rien n\'a été importé' : 'Contrôle réussi'}</legend>
          <p role="status">
            {bilan.lues} ligne(s) lue(s) · {bilan.articles_crees} article(s) {bilan.ecrit ? 'créé(s)' : 'à créer'} ·{' '}
            {bilan.stocks_modifies} stock(s) {bilan.ecrit ? 'modifié(s)' : 'à modifier'} · {bilan.inchanges} inchangé(s)
          </p>
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
