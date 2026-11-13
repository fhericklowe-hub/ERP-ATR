import { type FormEvent, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateFr } from '../achats/types'

export type Action = {
  id: number; evenement: number | null; evenement_numero: string; visite: number | null; visite_numero: string; statut: string; statut_libelle: string
  description: string; responsable: number; responsable_nom: string; echeance: string; faite_le: string | null; commentaire: string; en_retard: boolean; peut_agir: boolean
}
type Compte = { id: number; username: string; first_name: string; last_name: string }

/** Adresse du document d'où vient une action : l'événement ou la visite de sécurité. */
export const lienOrigine = (a: Action) => (a.visite ? `#/hse/visites/${a.visite}` : `#/hse/${a.evenement}`)

/** Les actions correctives d'un événement ou d'une visite : la liste, et le formulaire pour en décider une nouvelle. */
export default function ActionsCorrectives({ actions, origine, peutAjouter, peutAbandonner, recharger }: {
  actions: Action[]; origine: { evenement: number } | { visite: number }; peutAjouter: boolean; peutAbandonner: boolean; recharger: () => void
}) {
  const [comptes, setComptes] = useState<Compte[]>([])
  const [ac, setAc] = useState({ description: '', responsable: '', echeance: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    if (peutAjouter && comptes.length === 0) api<Page<Compte>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setComptes(p.results)).catch(() => undefined)
  }, [peutAjouter, comptes.length])

  async function envoyer(chemin: string, corps: object) {
    setErreur('')
    setEnCours(true)
    try {
      await api(chemin, { method: 'POST', body: JSON.stringify(corps) })
      recharger()
      return true
    } catch (err) {
      setErreur((err as Error).message)
      return false
    } finally {
      setEnCours(false)
    }
  }
  async function ajouter(ev: FormEvent) {
    ev.preventDefault()
    if (await envoyer('/hse/actions/', { ...origine, ...ac, responsable: Number(ac.responsable) })) setAc({ description: '', responsable: '', echeance: '' })
  }
  const terminer = (a: Action) => { const c = prompt('Commentaire (facultatif) :', ''); if (c !== null) envoyer(`/hse/actions/${a.id}/terminer/`, { commentaire: c }) }
  const abandonner = (a: Action) => { const c = prompt("Pourquoi l'action est-elle abandonnée ?", ''); if (c) envoyer(`/hse/actions/${a.id}/abandonner/`, { commentaire: c }) }

  if (actions.length === 0 && !peutAjouter) return null
  return (
    <fieldset>
      <legend>Actions correctives</legend>
      {actions.length === 0 && <p className="aide">Aucune action décidée.</p>}
      {actions.length > 0 && (
        <div className="defilant"><table>
          <thead><tr><th>Action</th><th>Responsable</th><th>Échéance</th><th>État</th><th></th></tr></thead>
          <tbody>{actions.map((a) => (
            <tr key={a.id}>
              <td>{a.description}{a.commentaire && <><br /><span className="aide">{a.commentaire}</span></>}</td><td>{a.responsable_nom}</td>
              <td>{dateFr(a.echeance)}</td>
              <td><span className={`pastille ${a.statut === 'FAITE' ? 'complete' : a.en_retard ? 'u1' : a.statut === 'A_FAIRE' ? 'partielle' : ''}`}>{a.en_retard ? 'En retard' : a.statut_libelle}{a.faite_le ? ` le ${dateFr(a.faite_le)}` : ''}</span></td>
              <td>{a.peut_agir && <button type="button" className="lien" disabled={enCours} onClick={() => terminer(a)}>Terminer</button>}{a.statut === 'A_FAIRE' && peutAbandonner && <> <button type="button" className="lien" disabled={enCours} onClick={() => abandonner(a)}>Abandonner</button></>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {peutAjouter && (
        <form className="grille" onSubmit={ajouter}>
          <label>Action à mener<input required maxLength={300} value={ac.description} onChange={(ev) => setAc({ ...ac, description: ev.target.value })} /></label>
          <label>Responsable<select required value={ac.responsable} onChange={(ev) => setAc({ ...ac, responsable: ev.target.value })}><option value="">Choisir</option>{comptes.map((c) => <option key={c.id} value={c.id}>{[c.last_name, c.first_name].filter(Boolean).join(' ') || c.username}</option>)}</select></label>
          <label>À faire avant le<input type="date" required value={ac.echeance} onChange={(ev) => setAc({ ...ac, echeance: ev.target.value })} /></label>
          <div className="actions"><button className="secondaire" disabled={enCours}>Ajouter l'action</button></div>
        </form>
      )}
    </fieldset>
  )
}
